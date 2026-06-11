# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Local development (recommended)
```bash
python dev.py               # starts Redis (Docker), FastAPI :8000, Celery worker, Next.js :3000
python dev.py --no-worker   # skip Celery (scans won't run, but API and frontend work)
```

### Individual services
```bash
# Backend API
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Celery worker — on Windows MUST use --pool=solo (billiard prefork fails on Windows)
cd backend && celery -A app.tasks.celery_app worker --loglevel=info --pool=solo

# Celery beat scheduler (scheduled scans, price broadcasts)
cd backend && celery -A app.tasks.celery_app beat --loglevel=info

# Frontend
cd apps/web && npm run dev
```

### Docker (production-like)
```bash
make up       # docker-compose up -d
make down     # docker-compose down
make logs     # tail api + worker logs
make install  # pip install + npm install
make clean    # remove __pycache__ and .next
```

Docker runs two separate workers: `worker-scans` (concurrency=2, queues: scans+default) and `worker-admin` (concurrency=1, queues: admin+backtests). `dev.py` merges all queues into a single `--pool=solo` worker.

Flower (Celery task monitor) is available at `http://localhost:5555` when running via Docker. Default auth: `admin / gate_flower_2024` (set via `FLOWER_USER` / `FLOWER_PASSWORD` env vars).

### Database
```bash
# Run all migrations in order against NeonDB
psql $DATABASE_URL -f backend/migrations/001_initial_schema.sql
psql $DATABASE_URL -f backend/migrations/002_stock_master.sql
psql $DATABASE_URL -f backend/migrations/003_performance_indexes.sql
psql $DATABASE_URL -f backend/migrations/004_architecture_v2.sql
psql $DATABASE_URL -f backend/migrations/005_backtest_per_stock.sql
psql $DATABASE_URL -f backend/migrations/006_backtest_streaming.sql  # required for streaming backtest progress
psql $DATABASE_URL -f backend/migrations/007_optimization_indexes.sql  # covering indexes for dashboard, signals, watchlist hot paths
```

Migration 006 adds `backtest_stock_results`, `total_symbols`, and `scanned_symbols` columns. The app degrades gracefully without it (skips per-stock persistence with a log warning) but streaming backtest results won't populate.

Migration 007 adds covering and partial indexes for the heaviest query paths (dashboard aggregation, signal list filtering, watchlist lifecycle, auto-exit scans). Safe to run on a live database — all statements use `CREATE INDEX IF NOT EXISTS`.

### Install dependencies
```bash
pip install -r backend/requirements.txt
cd apps/web && npm install
```

There is no test suite or linter configured. Run `python dev.py` and exercise the UI to verify behaviour.

## Environment

Copy `.env.example` to `.env` at the project root and set:
- `DATABASE_URL` — NeonDB (PostgreSQL 16) connection string
- `REDIS_URL` — defaults to `redis://localhost:6379/0`
- `ALLOWED_ORIGINS` — defaults to `http://localhost:3000`
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — optional, leave empty to disable
- `INTERNAL_SECRET` — token required by `/api/internal/*` endpoints (for external cron triggers)
- `SCAN_EXECUTOR_WORKERS` — thread pool size for scans (default: 4)
- `READ_REPLICA_URL` — optional NeonDB read replica; leave empty to use primary for all reads
- `GATE_CACHE_DIR` — override Parquet cache location (default: `../.gate_cache`)

The backend reads `.env` from `backend/../.env` (project root). Frontend reads from `apps/web/.env.local`.

## Repository Layout

```
gate_scanner/
├── backend/
│   ├── app/
│   │   ├── core/               # GATE scanner engine (the former gate_scanner/ package)
│   │   │   ├── config.py       # all engine tunables — no magic numbers in engines
│   │   │   ├── analysis/       # ema_engine, contraction_engine, structure_engine,
│   │   │   │                   # signal_engine, indicators, multi_timeframe
│   │   │   ├── backtester/     # walk-forward engine, metrics, portfolio, trade
│   │   │   ├── ranking/        # classifier, ranking_engine
│   │   │   ├── reporting/      # charting (Plotly), reporting, scan_report (HTML)
│   │   │   └── scanner/        # data_fetcher (yfinance + Parquet cache), pipeline,
│   │   │                       # universe/ (nse_universe, filters, stock_master_sync)
│   │   ├── agents/             # thin wrappers for the 5 pipeline stages
│   │   ├── routers/            # FastAPI route handlers (one file per domain)
│   │   ├── queries/            # raw asyncpg SQL — no ORM
│   │   ├── services/           # scan_service (async wrapper), ws_manager, alert_engine,
│   │   │                       # automation_service (auto paper trades), price_service,
│   │   │                       # stock_service (fundamentals enrichment thread pool)
│   │   ├── tasks/              # Celery: scanner_tasks, backtest_tasks, stock_tasks,
│   │   │                       # trading_tasks, celery_app
│   │   ├── models/             # Pydantic request/response models
│   │   ├── config.py           # runtime settings via pydantic-settings (env vars)
│   │   └── main.py             # FastAPI app, lifespan, WebSocket /ws endpoint
│   └── migrations/             # plain SQL — run manually with psql
├── apps/web/                   # Next.js 15 App Router frontend
│   ├── app/(dashboard)/        # route group — shared layout wraps all dashboard pages
│   │   │                       # pages: / (dashboard), /scanner, /paper-trading,
│   │   │                       # /portfolio, /alerts, /backtest, /stocks, /stocks/[symbol]
│   └── src/
│       ├── components/         # domain/ (SignalTable, GATEChart…), layout/, ui/
│       ├── store/              # Redux store + RTK Query slices in store/api/
│       ├── hooks/              # useWebSocket (single WS connection)
│       ├── lib/                # constants.ts (API_URL, colours), formatters.ts, theme.ts
│       └── types/              # TypeScript types (Signal, Portfolio, Alert…)
├── dev.py                      # all-in-one local dev launcher
├── docker-compose.yml
└── Makefile
```

## Architecture

### Infrastructure
- **Database**: NeonDB (PostgreSQL 16) via `asyncpg` connection pool. No ORM — raw SQL lives in `app/queries/`.
- **Cache/Broker**: Redis — Celery broker+backend, pub/sub for real-time events.
- **Workers**: Celery processes CPU-bound scan and backtest jobs off the FastAPI event loop.
- **Observability**: Prometheus metrics exposed at `/metrics` (via `app/metrics.py`). Structured logs via `structlog` with per-request `X-Request-ID` correlation — `ConsoleRenderer` in dev, swap for `JSONRenderer` in production. API docs at `/api/docs`. Extended health check at `/api/health/detailed` (DB pool stats, Redis ping, last scan info).
- **Rate limiting**: `slowapi` enforces 200 requests/minute per IP globally; `/api/health` and `/metrics` are exempt.

### Celery Beat schedule
| Task | Schedule | Purpose |
|---|---|---|
| `daily-post-market-scan` | 16:05 IST Mon–Fri | Full universe scan after market close |
| `weekly-stock-master-sync` | 06:00 UTC Sunday | Sync Nifty 50/Next 50 fundamentals |
| `fundamentals-enrichment-batch` | Every 15 min | Enrich stock master with fundamentals |
| `monitor-paper-trades` | Every 5 min (market hours) | Check SL/target hits, auto-exit positions |
| `broadcast-position-prices` | Every 2 min (market hours) | Push live price ticks to connected clients |

### Scan request flow
```
POST /api/scans/trigger
  → creates row in scans table (status=pending)
  → queues run_scan_task (Celery)
     → scan_service.run_scan_async()
        → pipeline.run_scan() in ThreadPoolExecutor
           progress published to Redis "scan:progress"
        → signals inserted into signals table
        → Redis "scan:complete" published
  → ws_manager fans out to all WebSocket clients
```

Backtest follows the same pattern via `POST /api/backtests/run` → `run_backtest_task` → streaming batch loop → `backtest:progress` channel.

### Redis pub/sub channels
`ws_manager.py` subscribes to all of these and fans out to every WebSocket client:

| Channel | Events published |
|---|---|
| `scan:progress` | `scan.started`, `scan.progress`, `scan.batch`, `scan.failed` |
| `scan:complete` | `scan.complete`, `backtest.complete` |
| `scan:batch` | `scan.batch` (streaming signal batches) |
| `scan:post_process` | `scan.post_process` (watchlist + auto-trades) |
| `price:update` | `price.update` (live price ticks) |
| `backtest:progress` | `backtest.batch_scanning`, `backtest.stock_complete` |

Adding a new real-time event requires: publishing to the correct channel in the backend task, handling the message type in `useWebSocket.ts`, and dispatching a Redux action.

### GATE scanner pipeline — 5 stages
Defined in `backend/app/core/scanner/pipeline.py`. Agents in `backend/app/agents/`:

1. **MarketScannerAgent** — parallel yfinance fetch via `ThreadPoolExecutor`; liquidity filter: price ≥ ₹20, 20d avg vol ≥ 100k.
2. **MTFAnalysisAgent** — runs `ema_engine`, `contraction_engine`, `structure_engine` per timeframe; `mtf_summary()` picks *leading TF* (smallest with GATE score ≥ threshold) and *confirmation TF* (next-larger agreeing TF).
3. **RiskManagementAgent** — builds concrete signal on the confirmation TF: Entry = close, SL = EMA200 of the next-smaller TF (from `config.SL_TIMEFRAME_MAP`), T1/T2/T3 = ATR-projected. Hard filters: RR(T1) ≥ 1.5, SL distance ≤ 12%.
4. **SignalRankingAgent** — computes `rank_score` (0–100) via `config.RANK_WEIGHTS`; classifies into INVESTMENT / SWING / POSITIONAL / WATCH / IGNORE via `config.CATEGORY_RULES`.
5. **ReportGenerationAgent** — writes CSV/JSON/HTML (only in standalone pipeline mode; web platform uses the DB instead).

### Backtest streaming
`run_backtest_task` splits the universe into batches of 10 (`STREAM_BATCH_SIZE`). Each batch runs `BacktestEngine` synchronously in a `ThreadPoolExecutor(max_workers=2)`, then persists trades + per-stock metrics to `backtest_stock_results` and publishes a `backtest.stock_complete` event. The browser accumulates results live via `backtestLive` in `wsSlice`. Rate limit on `POST /api/backtests/run` is 2/minute.

### Post-scan automation
After each scan completes, `automation_service.py` fires: WATCH-category signals above a rank threshold are added to the watchlist; INVESTMENT/SWING/POSITIONAL signals above `AUTO_TRADE_MIN_RANK` (default 50) automatically open paper trades. This publishes a `scan.post_process` event.

### Frontend data flow
- **RTK Query** (in `src/store/api/`) handles all REST calls with automatic cache and tag invalidation: `signalsApi`, `portfolioApi`, `alertsApi`, `marketApi`, `backtestApi`, `stockMasterApi`.
- **WebSocket** — `useWebSocket` hook manages one persistent `/ws` connection and dispatches Redux actions from `wsSlice` (scan progress, alert badges, price ticks, backtest streaming). Reconnects automatically after 3 s on disconnect; sends a `ping` every 25 s.
- **Backtest page** — exception: uses raw `fetch()` with 5 s polling instead of RTK Query, because backtests are one-shot long-running jobs rather than cached resources.

### Router versioning
All routers are mounted under both `/api` and `/api/v1` prefixes (see `main.py`). The `signals` router is marked legacy and will be unmounted in M5. New endpoints should be domain-namespaced (e.g., `/api/v1/stocks`, not `/api/v1/signals`).

Active routers: `dashboard`, `scans`, `signals` (legacy), `paper_trading`, `universe`, `watchlist`, `market`, `backtests`, `stock_master`, `internal`. URL prefixes to note: `stock_master` mounts at `/api/stocks` (not `/stock_master`); `paper_trading` mounts at `/api/paper-trading`. A `portfolio.py` router file exists but is **not mounted** — it is a legacy remnant. The `internal` router is the only router **not** dual-versioned; it mounts only at `/api/internal` (no `/api/v1/internal`). All `internal` endpoints require the `INTERNAL_SECRET` bearer token.

### Key design decisions

**Config split** — `backend/app/core/config.py` holds pure Python engine constants (GATE weights, EMA periods, SL map, category thresholds). `backend/app/config.py` holds runtime settings loaded from `.env` via `pydantic-settings`. Do not mix them.

**4h timeframe is synthesized** — yfinance has no native 4h interval. `data_fetcher.py` resamples 60m bars to 4h. Because `SL_TIMEFRAME_MAP["1d"] = "4h"`, the scanner always fetches 60m data when scanning the daily timeframe.

**Monthly blue-chip exception** — Nifty 50 stocks on the monthly timeframe correct to EMA100 (not EMA200). Both `symbol` and `timeframe` must be threaded through to `ema_engine.analyze()` for this branch to fire.

**Disk cache** — `.gate_cache/` holds Parquet files (1 h TTL) and universe `.txt` files (24 h TTL). Shared between Docker containers via a named volume. Override with `GATE_CACHE_DIR` env var.

**asyncpg serialization** — asyncpg returns `Decimal` for all `NUMERIC` columns and `UUID` objects. Every router must convert these before returning JSON: `Decimal → float`, `UUID → str`, dates → `.isoformat()`. Failing to do so causes `toFixed is not a function` errors in the frontend. Use the `_serialize()` helper pattern already present in each router.

**Windows Celery** — billiard's prefork pool uses POSIX shared semaphores that fail on Windows (`PermissionError: [WinError 5]`). Always start the worker with `--pool=solo` on Windows. `celery_app.py` sets `worker_pool="solo"` automatically when `sys.platform == "win32"`.

**Windows asyncpg in Celery tasks** — asyncpg requires `SelectorEventLoop` on Windows (Celery defaults to `ProactorEventLoop`). Any Celery task that calls asyncpg must set `asyncio.WindowsSelectorEventLoopPolicy()` before `asyncio.run(...)`. See `backtest_tasks.py` for the pattern.
