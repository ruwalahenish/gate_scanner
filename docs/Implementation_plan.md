# Advanced Personal Trading Intelligence Platform — Architecture Roadmap

**Project:** GATE Scanner → Trading Intelligence Platform  
**Stack:** Next.js 14 · MUI · Redux Toolkit · FastAPI · NeonDB (PostgreSQL) · Redis  
**Scope:** Personal/private use · No authentication · No broker APIs

---

## Context

The existing GATE Scanner is a well-architected 5-stage Python pipeline (~6,450 lines across 20 modules) that produces actionable trade signals using EMA-based GATE strategy. It has strong engines (EMA, GATE score 6-component, MTF analysis), a rich 27-field signal object, and a walk-forward backtester. What it lacks is a persistent, interactive, real-time front-end experience.

The upgrade is **not a rewrite** — it is a layering of infrastructure around a preserved Python core. Every existing engine file (`ema_engine.py`, `contraction_engine.py`, `structure_engine.py`, `signal_engine.py`, `multi_timeframe.py`, etc.) stays untouched. FastAPI wraps them as HTTP and WebSocket endpoints. The Next.js frontend consumes those endpoints.

---

## Table of Contents

1. [Technology Stack Decisions](#1-technology-stack-decisions)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Frontend Architecture](#3-frontend-architecture)
4. [Backend Architecture](#4-backend-architecture)
5. [Database Schema](#5-database-schema)
6. [API Design](#6-api-design)
7. [Folder Structure](#7-folder-structure)
8. [State Management Architecture](#8-state-management-architecture)
9. [Real-time & WebSocket Architecture](#9-real-time--websocket-architecture)
10. [Notification Architecture](#10-notification-architecture)
11. [Charting Strategy](#11-charting-strategy)
12. [Data Fetching Strategy](#12-data-fetching-strategy)
13. [Caching Strategy](#13-caching-strategy)
14. [Error Handling & Logging](#14-error-handling--logging)
15. [Security Best Practices](#15-security-best-practices)
16. [Performance Optimization](#16-performance-optimization)
17. [Rate Limiting Strategy](#17-rate-limiting-strategy)
18. [Deployment Architecture](#18-deployment-architecture)
19. [CI/CD Recommendations](#19-cicd-recommendations)
20. [Backup Strategy](#20-backup-strategy)
21. [Implementation Phases](#21-implementation-phases)
22. [Advanced & AI Features](#22-advanced--ai-features)
23. [Common Pitfalls to Avoid](#23-common-pitfalls-to-avoid)
24. [Package Reference](#24-package-reference)

---

## 1. Technology Stack Decisions

### Why FastAPI (not Django, not Flask, not Node.js)

The critical constraint: the scanning engines are 6,000+ lines of Python. Rewriting in TypeScript/Node.js would take months and introduce bugs. FastAPI lets you import and call `gate_scanner.*` modules directly from API endpoints.

| Criterion | FastAPI | Django | Flask | Express/Node |
|-----------|---------|--------|-------|--------------|
| Import existing Python engines | Native | Native | Native | Impossible |
| Async performance | Excellent | Mediocre | Poor | Excellent |
| WebSocket support | Built-in | Third-party | Third-party | Third-party |
| Auto OpenAPI docs | Built-in | Third-party | Third-party | Third-party |
| Startup time | Fast | Slow | Fast | Fast |

**Verdict:** FastAPI is the only choice that preserves your existing investment and adds production-grade async capabilities.

### Why asyncpg (not psycopg2, not SQLAlchemy, not Prisma)

- `asyncpg` is the fastest Python PostgreSQL driver (3–5× faster than psycopg2 for concurrent queries)
- Pure async, no thread pool overhead
- Supports prepared statements natively (critical for repeated scan inserts)
- Direct SQL keeps full control of query plans — no ORM "magic" N+1 queries

### Why Redis

- **Caching:** Hot scan results, live price snapshots, universe lists
- **Pub/Sub:** Scanner broadcasts signal updates; WebSocket workers subscribe and push to clients
- **Queues:** Alert engine job queue, scheduled scan jobs (Celery broker)
- **Rate limiting:** Token bucket counters for yfinance API calls
- **Session-like state:** Current paper portfolio state in memory (fast reads)

Redis is free on Upstash (serverless, 10k commands/day free tier) or self-hosted on a $5/mo VPS.

### Why RTK Query (not React Query, not SWR)

RTK Query is the data-fetching layer built into Redux Toolkit. Since Redux Toolkit is already the state management choice:
- One store, one devtools panel, zero impedance mismatch
- Automatic cache invalidation when mutations happen
- Built-in optimistic updates
- No extra dependency (it's inside `@reduxjs/toolkit`)

### Why TradingView Lightweight Charts (not Recharts/Chart.js for OHLCV)

- Free, MIT-licensed, open source
- Industry standard for financial charting
- Handles 100k+ candles without performance degradation
- Native candlestick, volume, and indicator overlay support
- Time-zone aware x-axis (critical for IST market hours)
- Use Recharts **alongside** it for portfolio analytics (pie, area charts)

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│                                                                      │
│  Next.js 14 App (App Router)                                        │
│  ├── MUI v6 Components                                              │
│  ├── Redux Toolkit + RTK Query                                      │
│  ├── TradingView Lightweight Charts (OHLCV)                         │
│  ├── Recharts (portfolio analytics)                                 │
│  └── WebSocket client (real-time signals/alerts)                    │
└─────────────┬───────────────────────────────┬───────────────────────┘
              │ HTTPS REST                    │ WSS
              ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API LAYER                                     │
│                                                                      │
│  FastAPI Application                                                │
│  ├── REST Routers (signals, portfolio, alerts, scans, universe)     │
│  ├── WebSocket Manager (pub/sub via Redis)                          │
│  ├── Background Task Queue (Celery + Redis)                         │
│  ├── Alert Engine (polling + event-driven)                          │
│  └── GATE Engine Adapter (imports gate_scanner.* directly)          │
└──────┬──────────────────────┬──────────────────────────────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐    ┌─────────────────────────────────────────────────┐
│  NeonDB      │    │  Redis (Upstash or self-hosted)                 │
│  PostgreSQL  │    │  ├── Cache (scan results, price data)           │
│              │    │  ├── Pub/Sub (real-time signal broadcast)       │
│  ├── scans   │    │  ├── Job Queue (Celery broker)                  │
│  ├── signals │    │  ├── Rate limit counters                        │
│  ├── trades  │    │  └── Paper portfolio fast-path state            │
│  ├── alerts  │    └─────────────────────────────────────────────────┘
│  ├── watchlist              │
│  ├── portfolio              ▼
│  └── ...     │    ┌─────────────────────────────────────────────────┐
└──────────────┘    │  yfinance / NSE Data                            │
                    │  (rate-limited, Parquet-cached in .gate_cache/) │
                    └─────────────────────────────────────────────────┘
```

---

## 3. Frontend Architecture

### App Router Page Structure

```
app/
├── layout.tsx                    ← Root: MUI ThemeProvider + Redux Provider
├── providers.tsx
├── (dashboard)/
│   ├── layout.tsx                ← Sidebar nav + top bar shell
│   ├── page.tsx                  ← Market overview dashboard
│   ├── signals/
│   │   ├── page.tsx              ← Signal scanner table
│   │   └── [symbol]/page.tsx    ← Symbol detail: MTF analysis + chart
│   ├── portfolio/
│   │   ├── page.tsx              ← Paper portfolio overview
│   │   ├── positions/page.tsx    ← Open positions table
│   │   └── history/page.tsx      ← Trade history + P&L
│   ├── watchlist/page.tsx
│   ├── alerts/page.tsx
│   ├── analytics/
│   │   ├── page.tsx              ← Win rate, CAGR, Sharpe, drawdown
│   │   └── backtest/page.tsx     ← Backtest runner + results
│   └── settings/page.tsx
```

### MUI Theme Configuration

```typescript
// lib/theme.ts
export const theme = createTheme({
  palette: {
    mode: "dark",
    primary:   { main: "#6366f1" },   // Indigo — signals, actions
    success:   { main: "#22c55e" },   // Green  — bullish, profit
    error:     { main: "#ef4444" },   // Red    — bearish, loss
    warning:   { main: "#f59e0b" },   // Amber  — watch, pending
    background: { default: "#0f0f12", paper: "#1a1a24" },
  },
  typography: {
    fontFamily: "'Inter Variable', sans-serif",
    body2: { fontVariantNumeric: "tabular-nums" },  // tabular numbers for prices
  },
});
```

### Component Architecture (3-Tier)

```
src/components/
├── ui/         ← Atomic: StatCard, PriceBadge, GATEBar, CategoryChip
├── domain/     ← Feature: SignalTable, PositionCard, AlertItem, MTFHeatmap
└── layout/     ← Structural: Sidebar, TopBar, PageShell, SplitPane
```

**Rule:** `ui/` has zero business logic. `domain/` connects to Redux. `layout/` handles responsive shells.

### Key Dashboard Pages

| Page | Core Components | Data Source |
|------|----------------|-------------|
| Dashboard `/` | Category counts, top 5 signals, portfolio strip, alert feed | RTK Query + WS |
| Signals `/signals` | MUI DataGrid, filter bar, expandable rows with MTF analysis | REST paginated |
| Symbol Detail `/signals/[symbol]` | TradingView chart + signal levels + MTF table | REST + OHLCV |
| Portfolio `/portfolio` | P&L cards, positions table, trade modal | REST + WS price updates |
| Analytics `/analytics` | Equity curve (Recharts), monthly heatmap, win rate | REST |
| Alerts `/alerts` | Alert table, create/dismiss modals | REST + WS |
| Backtest `/analytics/backtest` | Config form, Celery job progress bar, results | REST + WS |

---

## 4. Backend Architecture

### FastAPI Application

```python
# app/main.py — application bootstrap
app = FastAPI(title="GATE Trading Platform API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"])

@app.on_event("startup")
async def startup():
    app.state.db = await create_pool()       # asyncpg pool
    app.state.redis = await create_redis()   # aioredis

# Routers mounted at /api prefix
app.include_router(signals.router,   prefix="/api/signals")
app.include_router(portfolio.router, prefix="/api/portfolio")
app.include_router(alerts.router,    prefix="/api/alerts")
app.include_router(scans.router,     prefix="/api/scans")
app.include_router(universe.router,  prefix="/api/universe")
app.include_router(watchlist.router, prefix="/api/watchlist")
app.include_router(backtests.router, prefix="/api/backtests")
app.include_router(market.router,    prefix="/api/market")
```

### GATE Engine Adapter

Bridges FastAPI (async) to the CPU-bound Python scanning engines. Runs in a thread pool to avoid blocking the event loop.

```python
# app/services/engine_adapter.py
_executor = ThreadPoolExecutor(max_workers=cpu_count())

async def run_scan_async(universe: list[str], mode: str = "full") -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor,
        lambda: run_scan(universe=universe, mode=mode))

async def analyze_symbol_async(symbol: str, timeframes: list[str]) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _analyze_symbol, symbol, timeframes)
```

### Background Task System (Celery)

Scans take 60–300 seconds — they cannot be synchronous HTTP calls.

**Scan trigger flow:**
1. `POST /api/scans/trigger` → creates scan record (`status: pending`) → enqueues Celery task → returns `scan_id`
2. Celery worker runs scan → inserts signals → updates scan status to `done` → publishes to Redis channel `scan:complete`
3. FastAPI WebSocket handler subscribes → pushes `scan.complete` event to all connected clients
4. Frontend RTK Query invalidates `["Signal", "Scan"]` tags → auto-refetches

```python
# app/tasks/scanner_tasks.py
@celery_app.task(bind=True, max_retries=3)
def run_scheduled_scan(self, universe: list[str], scan_id: str):
    try:
        results = asyncio.run(run_scan_async(universe))
        asyncio.run(persist_scan_results(scan_id, results))
        publish_scan_complete(scan_id)  # Redis pub/sub
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### Alert Engine

Background `asyncio` service that polls price data every 60 seconds during market hours (09:15–15:30 IST, Mon–Fri) and evaluates all active alert conditions.

```python
# app/services/alert_engine.py
class AlertEngine:
    async def run(self):
        while True:
            if self._is_market_hours():
                await self._evaluate_all_alerts()
            await asyncio.sleep(60)

    def _condition_met(self, alert: dict, price: float) -> bool:
        t = alert["alert_type"]
        threshold = alert["threshold_value"]
        match t:
            case "price_above":    return price >= threshold
            case "price_below":    return price <= threshold
            case "gate_score_gte": return alert["gate_score"] >= threshold
            case "volume_spike":   return self._check_volume_spike(alert["symbol"])
            case _:                return False
```

---

## 5. Database Schema

All tables use UUID primary keys, `TIMESTAMPTZ` for timestamps, and `NUMERIC` for prices (avoids float precision issues).

```sql
-- ============================================================
-- SCAN HISTORY
-- ============================================================
CREATE TABLE scans (
    id              UUID PRIMARY KEY,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    mode            VARCHAR(20) NOT NULL DEFAULT 'daily',
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    universe_size   INT,
    passed_filter   INT,
    signals_found   INT,
    duration_sec    NUMERIC(8,2),
    error_message   TEXT
);
CREATE INDEX idx_scans_triggered ON scans(triggered_at DESC);

-- ============================================================
-- SIGNALS (one per scan × symbol)
-- ============================================================
CREATE TABLE signals (
    id                    UUID PRIMARY KEY,
    scan_id               UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    symbol                VARCHAR(20) NOT NULL,
    category              VARCHAR(20) NOT NULL,
    side                  VARCHAR(10),
    signal_timeframe      VARCHAR(10),
    sl_timeframe          VARCHAR(10),
    trend_direction       VARCHAR(10),
    entry                 NUMERIC(12,2),
    stop_loss             NUMERIC(12,2),
    sl_distance_pct       NUMERIC(6,3),
    t1                    NUMERIC(12,2),
    t2                    NUMERIC(12,2),
    t3                    NUMERIC(12,2),
    rr_t1                 NUMERIC(6,2),
    rr_t2                 NUMERIC(6,2),
    rr_t3                 NUMERIC(6,2),
    gate_strength         NUMERIC(6,2),
    volatility_compression NUMERIC(6,2),
    breakout_probability  NUMERIC(6,2),
    confidence            NUMERIC(6,2),
    rank_score            NUMERIC(6,2),
    mtf_alignment_pct     NUMERIC(6,2),
    structure_quality     NUMERIC(6,2),
    atr                   NUMERIC(12,4),
    htf_confirmed         BOOLEAN,
    correction_validated  BOOLEAN,
    bounce_sequence_valid BOOLEAN,
    fib_confluence        BOOLEAN,
    phase                 VARCHAR(30),
    trailing_plan         JSONB,
    reasoning             TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_signals_scan_symbol ON signals(scan_id, symbol);
CREATE INDEX idx_signals_symbol   ON signals(symbol);
CREATE INDEX idx_signals_category ON signals(category);
CREATE INDEX idx_signals_rank     ON signals(rank_score DESC);

-- ============================================================
-- PER-TIMEFRAME ANALYSIS (for MTF heatmap)
-- ============================================================
CREATE TABLE timeframe_analyses (
    id               UUID PRIMARY KEY,
    scan_id          UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    symbol           VARCHAR(20) NOT NULL,
    timeframe        VARCHAR(10) NOT NULL,
    ema_stack        VARCHAR(20),
    ema_compression  NUMERIC(6,2),
    correction_ema   SMALLINT,
    correction_type  VARCHAR(10),
    correction_depth SMALLINT,
    trend_direction  VARCHAR(10),
    trend_strength   NUMERIC(6,2),
    gate_score       NUMERIC(6,2),
    breakout_prob    NUMERIC(6,2),
    gate_components  JSONB,
    data_points      INT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tf_analyses ON timeframe_analyses(scan_id, symbol, timeframe);

-- ============================================================
-- PAPER PORTFOLIO
-- ============================================================
CREATE TABLE portfolio_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    initial_capital NUMERIC(14,2) NOT NULL DEFAULT 1000000,
    current_capital NUMERIC(14,2) NOT NULL DEFAULT 1000000,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE positions (
    id               UUID PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    side             VARCHAR(10) NOT NULL DEFAULT 'BUY',
    quantity         INT NOT NULL,
    avg_entry        NUMERIC(12,2) NOT NULL,
    stop_loss        NUMERIC(12,2),
    t1               NUMERIC(12,2),
    t2               NUMERIC(12,2),
    t3               NUMERIC(12,2),
    trailing_sl      NUMERIC(12,2),
    current_sl_level VARCHAR(10) DEFAULT 'original',
    signal_id        UUID REFERENCES signals(id),
    opened_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status           VARCHAR(20) NOT NULL DEFAULT 'open',
    notes            TEXT
);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_status ON positions(status);

CREATE TABLE trades (
    id           UUID PRIMARY KEY,
    position_id  UUID REFERENCES positions(id),
    symbol       VARCHAR(20) NOT NULL,
    side         VARCHAR(10) NOT NULL,
    quantity     INT NOT NULL,
    price        NUMERIC(12,2) NOT NULL,
    executed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_reason  VARCHAR(30),
    pnl_abs      NUMERIC(12,2),
    pnl_pct      NUMERIC(8,4),
    notes        TEXT
);
CREATE INDEX idx_trades_symbol   ON trades(symbol);
CREATE INDEX idx_trades_executed ON trades(executed_at DESC);

-- ============================================================
-- WATCHLIST
-- ============================================================
CREATE TABLE watchlist (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol   VARCHAR(20) NOT NULL UNIQUE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes    TEXT,
    tags     TEXT[]
);

-- ============================================================
-- ALERTS
-- ============================================================
CREATE TYPE alert_type_enum AS ENUM (
    'price_above', 'price_below',
    'gate_score_gte', 'gate_score_lte',
    'volume_spike', 'category_upgrade',
    'breakout_detected', 'sl_breach_warning', 'target_proximity'
);
CREATE TYPE alert_status_enum AS ENUM ('active', 'triggered', 'dismissed', 'expired');

CREATE TABLE alerts (
    id              UUID PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    alert_type      alert_type_enum NOT NULL,
    status          alert_status_enum NOT NULL DEFAULT 'active',
    threshold_value NUMERIC(12,2),
    timeframe       VARCHAR(10),
    message         TEXT,
    notify_via      TEXT[] DEFAULT ARRAY['web'],
    triggered_at    TIMESTAMPTZ,
    triggered_price NUMERIC(12,2),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_alerts_symbol ON alerts(symbol);
CREATE INDEX idx_alerts_status ON alerts(status);

-- ============================================================
-- BACKTESTER RESULTS
-- ============================================================
CREATE TABLE backtests (
    id              UUID PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL,
    completed_at    TIMESTAMPTZ,
    universe        TEXT[],
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    initial_capital NUMERIC(14,2) NOT NULL,
    final_equity    NUMERIC(14,2),
    total_trades    INT,
    winning_trades  INT,
    win_rate        NUMERIC(6,3),
    cagr            NUMERIC(8,4),
    sharpe_ratio    NUMERIC(8,4),
    max_drawdown    NUMERIC(8,4),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    config_snapshot JSONB
);

CREATE TABLE backtest_trades (
    id           UUID PRIMARY KEY,
    backtest_id  UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    symbol       VARCHAR(20) NOT NULL,
    entry_date   DATE NOT NULL,
    entry_price  NUMERIC(12,2) NOT NULL,
    sl_price     NUMERIC(12,2) NOT NULL,
    t1           NUMERIC(12,2),
    t2           NUMERIC(12,2),
    t3           NUMERIC(12,2),
    quantity     INT,
    timeframe    VARCHAR(10),
    category     VARCHAR(20),
    exit_date    DATE,
    exit_price   NUMERIC(12,2),
    exit_reason  VARCHAR(20),
    pnl_abs      NUMERIC(12,2),
    pnl_pct      NUMERIC(8,4),
    holding_days INT,
    rr_achieved  NUMERIC(8,4)
);
CREATE INDEX idx_bt_trades_backtest ON backtest_trades(backtest_id);

CREATE TABLE backtest_equity_curve (
    backtest_id    UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    curve_date     DATE NOT NULL,
    equity         NUMERIC(14,2),
    cash           NUMERIC(14,2),
    open_positions INT,
    PRIMARY KEY (backtest_id, curve_date)
);

-- ============================================================
-- MONITORING
-- ============================================================
CREATE TABLE scan_metrics (
    scan_id         UUID PRIMARY KEY REFERENCES scans(id),
    fetch_sec       NUMERIC(8,2),
    analysis_sec    NUMERIC(8,2),
    signal_gen_sec  NUMERIC(8,2),
    ranking_sec     NUMERIC(8,2),
    persist_sec     NUMERIC(8,2),
    symbols_fetched INT,
    cache_hits      INT,
    cache_misses    INT
);
```

---

## 6. API Design

### REST Endpoints

```
# Scans
GET    /api/scans                          ← List scan history (paginated)
POST   /api/scans/trigger                  ← Trigger new scan → returns {scan_id}
GET    /api/scans/{scan_id}                ← Scan status + summary
GET    /api/scans/{scan_id}/signals        ← All signals for a scan
GET    /api/scans/latest/signals           ← Latest scan's signals

# Signals
GET    /api/signals                        ← Paginated signals across all scans
GET    /api/signals/{symbol}              ← Signal history for a symbol
GET    /api/signals/{symbol}/analysis     ← Live MTF analysis (runs engine)
GET    /api/signals/{symbol}/chart-data   ← OHLCV + EMA data for charting

# Paper Portfolio
POST   /api/portfolio/buy                  ← Paper buy (symbol, qty, price)
POST   /api/portfolio/sell                 ← Paper sell (position_id, qty, price, reason)
GET    /api/portfolio/positions            ← Open positions with unrealized P&L
GET    /api/portfolio/trades               ← Trade history (paginated)
GET    /api/portfolio/summary              ← Equity, P&L, win rate, exposure
PUT    /api/portfolio/positions/{id}/sl   ← Update trailing SL
DELETE /api/portfolio/positions/{id}      ← Force close position

# Watchlist
GET    /api/watchlist
POST   /api/watchlist
DELETE /api/watchlist/{symbol}

# Alerts
GET    /api/alerts
POST   /api/alerts
PUT    /api/alerts/{id}
DELETE /api/alerts/{id}
POST   /api/alerts/{id}/dismiss

# Backtests
GET    /api/backtests
POST   /api/backtests/run
GET    /api/backtests/{id}
GET    /api/backtests/{id}/trades
GET    /api/backtests/{id}/equity-curve

# Market Data
GET    /api/market/price/{symbol}
GET    /api/market/prices                 ← Bulk prices (watchlist + portfolio)

# WebSocket
WS     /ws
```

### WebSocket Event Protocol

```typescript
type WSMessage = {
  type: WSEventType;
  payload: unknown;
  timestamp: string;  // ISO 8601
};

type WSEventType =
  | "scan.started"
  | "scan.progress"        // { scan_id, symbols_done, symbols_total }
  | "scan.complete"        // { scan_id, signals_count, top_signals: Signal[] }
  | "alert.triggered"      // { alert_id, symbol, message, price }
  | "price.update"         // { symbol, price, change_pct }
  | "position.pnl_update"  // { position_id, unrealized_pnl, unrealized_pnl_pct }
  | "ping" | "pong";
```

---

## 7. Folder Structure

### Frontend

```
apps/web/
├── app/
│   ├── layout.tsx
│   ├── providers.tsx
│   └── (dashboard)/
│       ├── layout.tsx
│       ├── page.tsx
│       ├── signals/
│       ├── portfolio/
│       ├── watchlist/
│       ├── alerts/
│       ├── analytics/
│       └── settings/
├── src/
│   ├── components/
│   │   ├── ui/           ← Atomic: StatCard, PriceBadge, GATEBar, CategoryChip
│   │   ├── domain/       ← Feature: SignalTable, PositionCard, MTFHeatmap
│   │   └── layout/       ← Structural: Sidebar, TopBar, SplitPane
│   ├── store/
│   │   ├── index.ts
│   │   ├── api/
│   │   │   ├── signalsApi.ts
│   │   │   ├── portfolioApi.ts
│   │   │   ├── alertsApi.ts
│   │   │   └── marketApi.ts
│   │   └── slices/
│   │       ├── uiSlice.ts
│   │       ├── wsSlice.ts
│   │       └── alertsSlice.ts
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useRealTimePnl.ts
│   │   └── useScanTrigger.ts
│   ├── lib/
│   │   ├── theme.ts
│   │   ├── formatters.ts    ← formatPrice, formatPct, formatRR
│   │   └── constants.ts
│   └── types/
│       ├── signal.ts
│       ├── portfolio.ts
│       └── alert.ts
├── next.config.ts
└── package.json
```

### Backend

```
backend/
├── app/
│   ├── main.py
│   ├── config.py              ← Pydantic Settings (reads .env)
│   ├── db.py                  ← asyncpg pool factory
│   ├── redis_client.py        ← aioredis factory
│   ├── dependencies.py        ← FastAPI Depends() factories
│   ├── routers/
│   │   ├── signals.py
│   │   ├── portfolio.py
│   │   ├── alerts.py
│   │   ├── scans.py
│   │   ├── universe.py
│   │   ├── watchlist.py
│   │   ├── backtests.py
│   │   └── market.py
│   ├── services/
│   │   ├── engine_adapter.py  ← Thread-pool wrapper for gate_scanner.*
│   │   ├── alert_engine.py    ← Alert evaluation loop
│   │   ├── price_service.py   ← Live price fetching + cache
│   │   ├── portfolio_service.py ← Paper trade execution logic
│   │   └── ws_manager.py      ← WebSocket connection registry
│   ├── tasks/
│   │   ├── celery_app.py
│   │   ├── scanner_tasks.py
│   │   └── backtest_tasks.py
│   ├── models/                ← Pydantic response models
│   │   ├── signal.py
│   │   ├── portfolio.py
│   │   ├── alert.py
│   │   └── scan.py
│   └── queries/               ← Raw SQL (no ORM)
│       ├── signals.py
│       ├── portfolio.py
│       ├── alerts.py
│       ├── scans.py
│       └── backtests.py
├── gate_scanner/              ← Existing package (symlinked or copied)
├── migrations/
│   └── 001_initial_schema.sql
├── pyproject.toml
└── requirements.txt
```

### SQL Query Module Pattern

```python
# app/queries/signals.py — all query modules follow this pattern
async def get_latest_signals(
    conn: asyncpg.Connection,
    category: str | None = None,
    min_rank: float = 0,
    limit: int = 50,
    offset: int = 0,
) -> list[asyncpg.Record]:
    return await conn.fetch("""
        SELECT s.* FROM signals s
        JOIN scans sc ON s.scan_id = sc.id
        WHERE sc.id = (SELECT id FROM scans WHERE status = 'done'
                       ORDER BY triggered_at DESC LIMIT 1)
        AND ($1::TEXT IS NULL OR s.category = $1)
        AND s.rank_score >= $2
        ORDER BY s.rank_score DESC
        LIMIT $3 OFFSET $4
    """, category, min_rank, limit, offset)

async def insert_signals_batch(conn, scan_id, signals):
    # Use asyncpg copy protocol — 10-50× faster than row-by-row execute()
    await conn.copy_records_to_table("signals",
        records=[_signal_to_row(scan_id, s) for s in signals],
        columns=["id", "scan_id", "symbol", ...])
```

---

## 8. State Management Architecture

### Store Layout

```typescript
// store/index.ts
export const store = configureStore({
  reducer: {
    ui:                    uiReducer,
    ws:                    wsReducer,
    [signalsApi.reducerPath]:   signalsApi.reducer,
    [portfolioApi.reducerPath]: portfolioApi.reducer,
    [alertsApi.reducerPath]:    alertsApi.reducer,
    [marketApi.reducerPath]:    marketApi.reducer,
  },
  middleware: (getDefault) => getDefault().concat(
    signalsApi.middleware, portfolioApi.middleware,
    alertsApi.middleware, marketApi.middleware,
  ),
});
```

### RTK Query API Slice Pattern

```typescript
// store/api/signalsApi.ts
export const signalsApi = createApi({
  reducerPath: "signalsApi",
  baseQuery: fetchBaseQuery({ baseUrl: process.env.NEXT_PUBLIC_API_URL }),
  tagTypes: ["Signal", "Scan"],
  endpoints: (builder) => ({
    getLatestSignals: builder.query<Signal[], SignalFilters>({
      query: (filters) => ({ url: "/signals", params: filters }),
      providesTags: ["Signal"],
    }),
    getSymbolAnalysis: builder.query<MTFAnalysis, string>({
      query: (symbol) => `/signals/${symbol}/analysis`,
      keepUnusedDataFor: 300,  // 5-minute cache for expensive analysis
    }),
    triggerScan: builder.mutation<{ scan_id: string }, ScanConfig>({
      query: (body) => ({ url: "/scans/trigger", method: "POST", body }),
      invalidatesTags: ["Signal", "Scan"],
    }),
  }),
});
```

### WebSocket → Redux Integration

```typescript
// hooks/useWebSocket.ts
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "scan.complete":
      dispatch(wsSlice.actions.scanCompleted(msg.payload.scan_id));
      dispatch(signalsApi.util.invalidateTags(["Signal", "Scan"]));
      break;
    case "alert.triggered":
      dispatch(wsSlice.actions.alertReceived());
      enqueueSnackbar(msg.payload.message, { variant: "warning" });
      break;
  }
};
```

---

## 9. Real-time & WebSocket Architecture

### Multi-Worker WebSocket Problem & Solution

FastAPI workers are separate processes. Redis Pub/Sub bridges them:

```
Worker 1 (scan runs here)    Worker 2 (client connected here)
         │                                │
         │ redis.publish("scan:done", payload)
         ▼                                ▼
    Redis Channel ──────────────────► WebSocket push to client
```

```python
# app/services/ws_manager.py
class WebSocketManager:
    _connections: set[WebSocket] = set()

    async def connect(self, ws): await ws.accept(); self._connections.add(ws)
    def disconnect(self, ws):    self._connections.discard(ws)

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        dead = set()
        for ws in self._connections:
            try:   await ws.send_text(data)
            except: dead.add(ws)
        self._connections -= dead

    async def listen_redis(self, redis):
        pubsub = redis.pubsub()
        await pubsub.subscribe("scan:progress", "scan:complete", "alert:triggered", "price:update")
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await self.broadcast(json.loads(msg["data"]))
```

### Keepalive

Frontend sends `"ping"` every 25 seconds. Backend replies `{"type":"pong"}`. This keeps WebSocket connections alive through nginx/load-balancer idle timeouts.

---

## 10. Notification Architecture

### Three Channels (All Free)

```
Alert triggered
    │
    ├── Web: Browser Notification API (works while tab is open)
    ├── Toast: WebSocket → frontend → notistack Snackbar
    └── Telegram: Free Bot API (mobile push, even when browser closed)
```

### Telegram Integration

```python
# app/services/telegram_notifier.py
class TelegramNotifier:
    async def send_signal_alert(self, signal: dict):
        emoji = "🟢" if signal["side"] == "BUY" else "🔴"
        msg = (
            f"{emoji} <b>{signal['symbol']}</b> — {signal['category']}\n"
            f"Entry: ₹{signal['entry']:.2f} | SL: ₹{signal['stop_loss']:.2f}\n"
            f"T1: ₹{signal['t1']:.2f} | RR: {signal['rr']['T1']:.1f}x\n"
            f"GATE: {signal['gate_strength']:.0f} | Rank: {signal['rank_score']:.0f}"
        )
        await self.send(msg)
```

---

## 11. Charting Strategy

### Library by Chart Type

| Chart Type | Library | Reason |
|-----------|---------|--------|
| OHLCV candlestick + EMA overlays | TradingView Lightweight Charts v5 | Financial-grade, 100k candles, free |
| Portfolio equity curve | Recharts AreaChart | Simplest time-series area in React |
| Monthly returns heatmap | Custom MUI Grid + alpha(color, score/100) | No library needed |
| Win/loss distribution | Recharts BarChart | Simple histogram |
| MTF heatmap (GATE strength) | Custom MUI Table | Built from MUI primitives |
| Portfolio allocation | Recharts PieChart | 5 lines of code |
| Trade duration vs RR | Recharts ScatterChart | Built-in |

### TradingView Chart Component

```typescript
// components/domain/GATEChart.tsx — "use client"
export function GATEChart({ data, emas, signal }) {
  // Creates chart with dark theme matching MUI palette
  // Adds candlestick series + EMA20/50/100/200 line series
  // Adds horizontal lines for entry (indigo), SL (red), T1/T2/T3 (green gradient)
  // ResizeObserver handles container width changes
  // Cleanup: chart.remove() + observer.disconnect()
}
```

---

## 12. Data Fetching Strategy

### Tiered Freshness Model

| Data | TTL | Strategy |
|------|-----|----------|
| Price data | 60s | Poll during market hours only |
| GATE signals | 1h | Invalidated on new scan complete (WS) |
| MTF analysis | 5min | `keepUnusedDataFor: 300` in RTK Query |
| Universe list | 24h | Matches existing gate_scanner behavior |
| Trade history | ∞ | DB is source of truth, no polling |
| Backtest results | ∞ | Immutable once computed |

### Market Hours Polling

```typescript
// RTK Query: only poll during IST market hours
const { data } = useGetPositionsQuery(undefined, {
  pollingInterval: isMarketHours() ? 60_000 : 0,
});

function isMarketHours(): boolean {
  const ist = new Date(new Date().toLocaleString("en-US", { timeZone: "Asia/Kolkata" }));
  const day = ist.getDay();
  if (day === 0 || day === 6) return false;
  const t = ist.getHours() * 60 + ist.getMinutes();
  return t >= 555 && t <= 930;  // 9:15 to 15:30
}
```

---

## 13. Caching Strategy

### Three-Layer Cache

```
Layer 1: Browser (RTK Query keepUnusedDataFor)
    signals: 5min · analysis: 5min · portfolio: 30s

Layer 2: Redis (FastAPI response cache)
    scan results: 1h · price data: 60s · universe: 24h

Layer 3: Disk (.gate_cache/ Parquet files — unchanged from existing code)
    OHLCV data: 1h TTL · universe .txt: 24h TTL
```

### Cache Invalidation Rules

| Event | Invalidate |
|-------|-----------|
| Scan completed | Redis: `latest:signals` · Frontend RTK: `["Signal", "Scan"]` |
| Portfolio buy/sell | Redis: `portfolio:summary`, `portfolio:positions` |
| Alert triggered | Redis: `alerts:active` |

---

## 14. Error Handling & Logging

### Backend Error Hierarchy

```python
# app/exceptions.py
class GATEBaseError(Exception):
    status_code: int = 500; detail: str = "Internal error"

class ScanInProgressError(GATEBaseError):
    status_code = 409; detail = "A scan is already running"

class SymbolNotFoundError(GATEBaseError):
    status_code = 404; detail = "Symbol not found in universe"

class InsufficientCapitalError(GATEBaseError):
    status_code = 422; detail = "Insufficient virtual capital"

class DataFetchError(GATEBaseError):
    status_code = 503; detail = "Market data temporarily unavailable"
```

### Structured Logging

```python
# structlog — JSON output, filterable in any log aggregator
log.info("scan_completed", scan_id=str(scan_id), signals_found=42, duration_sec=87.3)
log.error("data_fetch_failed", symbol="RELIANCE", error=str(e))
```

---

## 15. Security Best Practices

Even without authentication, these protections are required:

- **Bind to localhost** — FastAPI on `127.0.0.1:8000`, not `0.0.0.0`
- **HTTPS via nginx + Let's Encrypt** — even for personal use
- **CORS locked** — `allow_origins=["https://yourdomain.com"]`, never `"*"`
- **Parameterized queries only** — `conn.fetch("...WHERE symbol = $1", symbol)` — never f-string SQL
- **Pydantic input validation** — all request bodies validated with strict field patterns (`pattern=r"^[A-Z0-9\-\.&]{1,20}$"`)
- **Secrets in `.env`** — never in source code; `.env` in `.gitignore`
- **Redis lock for concurrent scans** — `SET scan:running 1 NX EX 600` prevents double-scan

---

## 16. Performance Optimization

### Backend

- `asyncpg` pool: `min_size=5, max_size=20` — reuse connections, never open/close per request
- Batch inserts: `asyncpg.copy_records_to_table` — 10–50× faster than row-by-row `execute()`
- Thread pool: `max_workers=cpu_count()` for CPU-bound GATE engine calls
- `GZipMiddleware`: signal list responses can be 500KB+, compress them
- Prepared statements: asyncpg caches query plans automatically on first use

### Frontend

- Server Components for signal tables — initial render on server, no hydration cost
- MUI DataGrid built-in virtualization for 500+ row tables
- Lazy-load TradingView chart (~200KB) — only when signal row is expanded
- `useMemo` for derived analytics: win rate, total P&L across positions
- `next/font` with Inter variable font, Latin subset only

---

## 17. Rate Limiting Strategy

```python
# app/services/rate_limiter.py — Token bucket for yfinance calls
class TokenBucketLimiter:
    def __init__(self, rate: float = 100, per: float = 60):
        # 100 requests per 60 seconds
        ...

    async def acquire(self, tokens: int = 1):
        # Async wait if bucket is empty
        ...

yfinance_limiter = TokenBucketLimiter(rate=100, per=60)
# Applied before every yfinance call in engine_adapter.py
```

Scan jobs batch-fetch to minimize total API call count. Endpoint-level rate limiting via `slowapi`: expensive analysis endpoint capped at 10/minute.

---

## 18. Deployment Architecture

### Recommended: Single VPS (~$6/mo)

```
DigitalOcean / Railway / Render
├── nginx (port 443, HTTPS)
│   ├── /          → Next.js :3000
│   ├── /api       → FastAPI :8000 (timeout: 300s for scans)
│   └── /ws        → FastAPI :8000 (Upgrade: websocket, timeout: 86400s)
├── pm2 or systemd:
│   ├── next start
│   ├── uvicorn app.main:app --workers 2
│   ├── celery -A app.tasks.celery_app worker
│   └── celery -A app.tasks.celery_app beat  (scheduled scans at 4 PM IST)
└── Redis (Docker container or systemd)
NeonDB (cloud — free tier: 0.5GB)
```

### Docker Compose (Development)

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    volumes: ["./.gate_cache:/app/.gate_cache"]
    depends_on: [redis]
  worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker
    depends_on: [redis]
  web:
    build: ./apps/web
    ports: ["3000:3000"]
  redis:
    image: redis:7-alpine
```

---

## 19. CI/CD Recommendations

### GitHub Actions (Free)

```yaml
# .github/workflows/ci.yml
jobs:
  backend:
    - pip install requirements.txt
    - python -m pytest backend/tests/

  frontend:
    - npm ci && npm run build && npm run type-check

  deploy:
    if: push to main
    - SSH to VPS → git pull → docker-compose up -d --build → run migrations
```

---

## 20. Backup Strategy

- **NeonDB**: `pg_dump` daily via cron at 2 AM IST, keep 30 days of `.sql.gz` files. NeonDB free tier includes 7-day PITR.
- **.gate_cache/ Parquet files**: Not backed up — ephemeral, rebuilt from yfinance on demand.
- **config.py / .env**: Store `.env.example` (template) in git; back up actual `.env` to encrypted private repo.

---

## 21. Implementation Phases

### Phase 0 — Foundation `Week 1–2` `Medium`

- [ ] Monorepo: `apps/web` (Next.js) + `backend/` (FastAPI)
- [ ] NeonDB: run `001_initial_schema.sql`
- [ ] FastAPI: asyncpg pool, health endpoint, CORS
- [ ] Next.js: MUI dark theme, Redux store, RTK Query base
- [ ] Docker Compose: all services running locally
- [ ] Deploy skeleton to VPS with nginx + HTTPS

**Deliverable:** `GET /api/health` returns `{"ok": true}`. MUI dark sidebar renders.

---

### Phase 1 — Signal Pipeline Integration `Week 3–4` `High`

- [ ] `engine_adapter.py`: thread-pool wrapper for `run_scan()`
- [ ] Celery: scan task queue + Redis broker
- [ ] `POST /api/scans/trigger` → `scan_id` response
- [ ] Worker: run scan → insert signals → publish Redis event
- [ ] WebSocket manager: Redis subscribe → push `scan.complete` to clients
- [ ] Signal router: paginated + filtered `GET /api/scans/latest/signals`
- [ ] Frontend: MUI DataGrid signal table, filter bar, category badges

**Deliverable:** Click "Run Scan" → spinner → signal table populates.

---

### Phase 2 — Paper Trading `Week 5–6` `Medium`

- [ ] `portfolio_service.py`: buy/sell execution, capital tracking
- [ ] API: buy, sell, positions, trade history, summary endpoints
- [ ] Frontend: Portfolio page, P&L cards, positions table
- [ ] Real-time P&L: WS price updates → Redux → unrealized P&L column
- [ ] Trade modal: pre-filled with signal entry/SL/T1 values

**Deliverable:** Click signal → Buy → position appears with live P&L.

---

### Phase 3 — Charts & Market Intelligence `Week 7–8` `High`

- [ ] `GET /api/signals/{symbol}/chart-data`: OHLCV + EMA data
- [ ] `GATEChart` component: TradingView with EMA20/50/100/200 overlays
- [ ] Signal level lines: entry (indigo), SL (red), T1/T2/T3 (green gradient)
- [ ] MTF heatmap: GATE scores by symbol × timeframe grid
- [ ] Symbol detail: chart + MTF table side-by-side
- [ ] Watchlist page: add/remove, mini sparklines

**Deliverable:** Expand signal row → TradingView chart with all signal levels.

---

### Phase 4 — Alert Engine `Week 9–10` `Medium`

- [ ] `alert_engine.py`: 9-condition polling loop
- [ ] API: CRUD for alerts
- [ ] Frontend: Alert management page + unread badge in top bar
- [ ] WS push `alert.triggered` → notistack toast
- [ ] Telegram integration (optional): bot token in `.env`

**Deliverable:** Create price-above alert → gets triggered → toast notification.

---

### Phase 5 — Analytics & Backtest UI `Week 11–12` `Medium`

- [ ] Analytics: equity curve (Recharts AreaChart), monthly returns heatmap, win rate, Sharpe
- [ ] Backtest runner: form → Celery task → progress bar → results
- [ ] Backtest results: metrics card + equity chart + trade table

**Deliverable:** Run backtest from UI → equity curve + trade-by-trade analysis.

---

### Phase 6 — Polish & Advanced Features `Week 13–16` `Medium`

- [ ] Command palette (`Ctrl+K`) — fuzzy jump to symbol/page/action
- [ ] Keyboard shortcuts: `s` scan, `b` buy, `Esc` close modals
- [ ] Scan scheduler UI (mirrors `scheduler.py` — set time, universe, mode)
- [ ] Settings page: adjust GATE weights/thresholds, stored in DB
- [ ] Export: download signals.csv, trade history.csv from UI
- [ ] Mobile-responsive layout
- [ ] PWA: `manifest.json` + service worker

**Deliverable:** Full personal trading terminal accessible from phone browser.

---

## 22. Advanced & AI Features

### Signal Reasoning Explainer `Low Complexity`

Use Claude API (`claude-sonnet-4-6`) to reformat the existing `reasoning` field into a concise professional trade thesis with key risks. The raw reasoning text from `signal_engine.py` is already structured — Claude just makes it readable.

### Pattern Recognition Alerts `Medium Complexity`

Add candlestick pattern detection (Hammer, Engulfing, Doji, Morning Star) as a new alert type. Rule-based detection on OHLCV, no ML required.

### Portfolio Risk Analyzer `Medium Complexity`

Auto-compute correlation between open positions, flag over-concentration by EMA correction level or sector, suggest trim candidates.

### Scan Digest (Telegram/Email) `Low Complexity`

After each post-market scan: auto-generate a 10-line summary (top 3 signals, positions that hit targets, alerts triggered) and send via Telegram Bot.

### AI Trade Journal `Low Complexity`

When closing a position, Claude auto-generates a trade review: did you follow the trailing plan, what category was it, what was the outcome relative to expectancy.

### Strategy Config Tuner `High Complexity`

Grid-search GATE parameters (score threshold ± 5, BB percentile ± 5) via multiple backtests and display a Sharpe ratio heatmap — identifies optimal config for your universe.

### Professional Terminal Features

- **Scan diff**: compare today's signals vs yesterday's, highlight new entries/exits
- **Time-in-stage tracker**: bars-since-entry vs expected holding period from signal TF
- **Nifty 50 heatmap**: colored tiles by GATE strength (Bloomberg-style)
- **Multi-symbol comparison**: 2–4 symbol side-by-side chart view

---

## 23. Common Pitfalls to Avoid

### Architecture

- **Never put scan logic in request handlers.** Scans take 60–300s. Always Celery.
- **Never use asyncio in Celery tasks directly.** Use `asyncio.run()` inside tasks.
- **Never use Redis as source of truth** for portfolio positions — Redis is cache, PostgreSQL is truth.
- **Never run two scans concurrently** — Redis lock: `SET scan:running 1 NX EX 600`.

### Frontend

- **Never render 500+ rows without virtualization.** Use DataGrid's built-in or `@tanstack/react-virtual`.
- **Never hardcode IST market hours.** Use `date-fns-tz` with `"Asia/Kolkata"`.
- **Never use `useEffect` for data fetching.** Use RTK Query's `useQuery`.
- **Never import TradingView in a Server Component.** Add `"use client"` to chart wrapper.

### Data

- **Never store prices as JavaScript float.** Use `NUMERIC` in PostgreSQL, `Decimal` in Python, strings in JSON.
- **Never build SQL strings dynamically.** Always use asyncpg parameterized queries (`$1`, `$2`).
- **Never assume yfinance symbol format.** Normalize `.NS`/`.BO` consistently in `data_fetcher.py`.

### Operational

- **Never skip migration files.** Even personal projects need `migrations/` with sequential numbering.
- **Never commit `.env`.** Check `.gitignore` before first push.
- **Monitor NeonDB storage.** Free tier = 0.5GB. At 200 signals/scan × 365 scans/year ≈ 73k rows/year — fine, but watch it.

---

## 24. Package Reference

### Backend

```toml
[tool.poetry.dependencies]
python          = "^3.12"
fastapi         = "^0.115"
uvicorn         = {extras=["standard"], version="^0.32"}
asyncpg         = "^0.30"
aioredis        = "^2.0"
celery          = {extras=["redis"], version="^5.4"}
pydantic        = "^2.10"
pydantic-settings = "^2.7"
httpx           = "^0.28"
structlog       = "^24.4"
slowapi         = "^0.1.9"
anthropic       = "^0.40"       # Optional: AI features
python-multipart= "^0.0.12"
```

### Frontend

```json
{
  "dependencies": {
    "next":                   "^15.1",
    "@mui/material":          "^6.3",
    "@mui/x-data-grid":       "^7.23",
    "@emotion/react":         "^11.14",
    "@emotion/styled":        "^11.14",
    "@reduxjs/toolkit":       "^2.5",
    "react-redux":            "^9.2",
    "lightweight-charts":     "^5.0",
    "recharts":               "^2.15",
    "notistack":              "^3.0",
    "date-fns":               "^4.1",
    "date-fns-tz":            "^3.2",
    "decimal.js":             "^10.4"
  }
}
```

### Phase 6+ Optional

```
@tanstack/react-virtual   ← Table virtualization
cmdk                      ← Command palette (Ctrl+K)
jspdf                     ← PDF export
xlsx                      ← Excel export
```

---

## Complexity & Timeline Estimate

| Phase | Complexity | Est. Hours |
|-------|-----------|-----------|
| 0: Foundation | Medium | 16h |
| 1: Signal pipeline | High | 24h |
| 2: Paper trading | Medium | 20h |
| 3: Charts | High | 24h |
| 4: Alert engine | Medium | 16h |
| 5: Analytics + backtest UI | Medium | 20h |
| 6: Polish + AI features | Medium | 24h |
| **Total** | | **~144h** |

At 2 hours/day → ~72 days (2.5 months) for a solo developer who is also the domain expert.

---

## Summary Decision Matrix

| Decision | Choice | Killer Reason |
|---------|--------|---------------|
| Backend language | Python (FastAPI) | 6,400 lines of Python engines — preserve them |
| DB driver | asyncpg | Fastest async PostgreSQL, no ORM bloat |
| Real-time | WebSocket + Redis Pub/Sub | Multi-worker safe |
| OHLCV charts | TradingView Lightweight Charts | Only free library built for financial data at scale |
| State management | RTK Query + Redux Toolkit | One tool for server cache + UI state |
| Job queue | Celery + Redis | Scans are 60–300s, must be async |
| Hosting | Single VPS ($6/mo) | Personal tool doesn't need Kubernetes |
| Alerts | Polling + Telegram Bot | Free, zero paid service dependency |
