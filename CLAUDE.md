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

# Frontend
cd apps/web && npm run dev
```

### Docker (production-like)
```bash
make up       # docker-compose up -d
make down     # docker-compose down
make logs     # tail api + worker logs
```

### Database
```bash
# First-time setup — run migration against NeonDB
psql $DATABASE_URL -f backend/migrations/001_initial_schema.sql
```

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
│   │   │                       # universe/ (nse_universe, filters)
│   │   ├── agents/             # thin wrappers for the 5 pipeline stages
│   │   ├── routers/            # FastAPI route handlers (one file per domain)
│   │   ├── queries/            # raw asyncpg SQL — no ORM
│   │   ├── services/           # scan_service (async wrapper), ws_manager, alert_engine
│   │   ├── tasks/              # Celery: scanner_tasks, backtest_tasks, celery_app
│   │   ├── models/             # Pydantic request/response models
│   │   ├── config.py           # runtime settings via pydantic-settings (env vars)
│   │   └── main.py             # FastAPI app, lifespan, WebSocket /ws endpoint
│   └── migrations/             # plain SQL — run manually with psql
├── apps/web/                   # Next.js 15 App Router frontend
│   ├── app/(dashboard)/        # page routes (signals, portfolio, alerts, backtest…)
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

Backtest follows the same pattern via `POST /api/backtests/run` → `run_backtest_task` → `BacktestEngine.run()`.

### GATE scanner pipeline — 5 stages
Defined in `backend/app/core/scanner/pipeline.py`. Agents in `backend/app/agents/`:

1. **MarketScannerAgent** — parallel yfinance fetch via `ThreadPoolExecutor`; liquidity filter: price ≥ ₹20, 20d avg vol ≥ 100k.
2. **MTFAnalysisAgent** — runs `ema_engine`, `contraction_engine`, `structure_engine` per timeframe; `mtf_summary()` picks *leading TF* (smallest with GATE score ≥ threshold) and *confirmation TF* (next-larger agreeing TF).
3. **RiskManagementAgent** — builds concrete signal on the confirmation TF: Entry = close, SL = EMA200 of the next-smaller TF (from `config.SL_TIMEFRAME_MAP`), T1/T2/T3 = ATR-projected. Hard filters: RR(T1) ≥ 1.5, SL distance ≤ 12%.
4. **SignalRankingAgent** — computes `rank_score` (0–100) via `config.RANK_WEIGHTS`; classifies into INVESTMENT / SWING / POSITIONAL / WATCH / IGNORE via `config.CATEGORY_RULES`.
5. **ReportGenerationAgent** — writes CSV/JSON/HTML (only in standalone pipeline mode; web platform uses the DB instead).

### Frontend data flow
- **RTK Query** (in `src/store/api/`) handles all REST calls with automatic cache and tag invalidation: `signalsApi`, `portfolioApi`, `alertsApi`, `marketApi`.
- **WebSocket** — `useWebSocket` hook manages one persistent `/ws` connection and dispatches Redux actions from `wsSlice` (scan progress, alert badges, price ticks).
- **Backtest page** — exception: uses raw `fetch()` with 5 s polling instead of RTK Query, because backtests are one-shot long-running jobs rather than cached resources.

### Key design decisions

**Config split** — `backend/app/core/config.py` holds pure Python engine constants (GATE weights, EMA periods, SL map, category thresholds). `backend/app/config.py` holds runtime settings loaded from `.env` via `pydantic-settings`. Do not mix them.

**4h timeframe is synthesized** — yfinance has no native 4h interval. `data_fetcher.py` resamples 60m bars to 4h. Because `SL_TIMEFRAME_MAP["1d"] = "4h"`, the scanner always fetches 60m data when scanning the daily timeframe.

**Monthly blue-chip exception** — Nifty 50 stocks on the monthly timeframe correct to EMA100 (not EMA200). Both `symbol` and `timeframe` must be threaded through to `ema_engine.analyze()` for this branch to fire.

**Disk cache** — `.gate_cache/` holds Parquet files (1 h TTL) and universe `.txt` files (24 h TTL). Shared between Docker containers via a named volume. Override with `GATE_CACHE_DIR` env var.

**asyncpg serialization** — asyncpg returns `Decimal` for all `NUMERIC` columns and `UUID` objects. Every router must convert these before returning JSON: `Decimal → float`, `UUID → str`, dates → `.isoformat()`. Failing to do so causes `toFixed is not a function` errors in the frontend.

**Windows Celery** — billiard's prefork pool uses POSIX shared semaphores that fail on Windows (`PermissionError: [WinError 5]`). Always start the worker with `--pool=solo` on Windows. `celery_app.py` sets `worker_pool="solo"` automatically when `sys.platform == "win32"`.
