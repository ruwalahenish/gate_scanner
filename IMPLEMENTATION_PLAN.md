# GATE Scanner — Architectural & UI/UX Transformation Plan

> **Process:** Each milestone requires explicit approval before the next begins.
> After completing a milestone, a summary is provided and implementation pauses for confirmation.

---

## Architecture After Transformation

### Navigation (6 items)
| Route | Page |
|-------|------|
| `/` | Dashboard — unified stats + analytics |
| `/stocks` | Master Stocks — central registry |
| `/scanner` | GATE Scanner — primary scan workflow |
| `/watchlist` | Watchlist — auto-managed from WATCH signals |
| `/paper-trading` | Paper Trading — auto-managed from BUY signals |
| `/backtest` | Backtesting — strategy validation |

### Removed Modules
- **Alerts** — page, API, service, DB table
- **Portfolio** (manual) — replaced by automated Paper Trading
- **Analytics** (standalone) — merged into Dashboard
- **Settings** — removed entirely
- **Signals** (standalone page) — results surfaced via Scanner page

### Signal Terminology
| Internal | Display |
|----------|---------|
| INVESTMENT / SWING / POSITIONAL | BUY Opportunity |
| WATCH | Watch |
| IGNORE | No Action |

### Job Processing
- No continuously running polling loops
- Daily scan via Celery Beat (post-market 16:00 IST, configurable)
- On-demand scan via UI
- Auto-watchlist: WATCH signals → watchlist on scan complete
- Auto-paper-trades: BUY signals (rank ≥ 65) → positions on scan complete

---

## Milestones — ALL COMPLETE ✅

### Milestone 1 — Backend Cleanup & Module Removal ✅ DONE
**Scope:** Backend only — remove alerts, signals standalone router, alert engine, and manual portfolio router.
- Delete: `alerts.py` router/service/queries/model, `alert_engine.py`
- Create: `paper_trading.py` router + model (stub replacing portfolio)
- Migrate signals endpoints → scans router
- Update: `main.py`, `ws_manager.py`, `scanner_tasks.py`

**Acceptance:** `python dev.py` starts clean; scan, stock master, backtest, watchlist endpoints all return 200.

---

### Milestone 2 — Database Schema Migration
**Scope:** New migration file only. No app code changes.
- Drop `alerts` table
- Enhance `watchlist` table (status, signal_id, GATE data, source)
- Add `watchlist_history` table
- Add `auto_created` + `creation_source` columns to `positions`
- Add `scan_schedule` singleton table

---

### Milestone 3 — Automated Workflows & Scheduled Processing
**Scope:** Backend business logic.
- New `automation_service.py`: auto-watchlist, auto-paper-trades, auto-exit
- Extend `scanner_tasks.py` with post-scan hooks
- Configure Celery Beat daily scan + weekly stock sync
- New `GET/PUT /api/scan-schedule` endpoints
- Expand `paper_trading` router with summary/positions/trades/performance

---

### Milestone 4 — API Normalization & Dashboard Endpoint
**Scope:** Backend API layer.
- New `GET /api/dashboard` endpoint (single call, Redis-cached 60s)
- Add `display_status` + `display_category` to signal responses
- New `GET /api/scans/{scan_id}/signals` + `GET /api/scans/latest/signals` with status filter
- Enrich `GET /api/watchlist` with signal levels + history endpoint

---

### Milestone 5 — Frontend Cleanup & Navigation Restructure
**Scope:** Frontend only.
- Delete: alerts, analytics, settings pages + alertsApi
- Add stubs: `/scanner`, `/paper-trading`, `/backtest` pages
- Update sidebar to 6 items; update TopBar (remove alerts badge, capital display)
- New RTK Query slices: `scannerApi`, `paperTradingApi`, `watchlistApi`
- Update store, wsSlice, useWebSocket hook, types

---

### Milestone 6 — Dashboard Redesign
**Scope:** Frontend — `/` page.
- Single `useGetDashboardQuery()` fetch
- 4-stat bar: BUY Signals / Watching / Open Trades / Win Rate
- Recent opportunities + recent trades panels
- Watchlist status + paper trading P&L + system health panels
- Loading skeletons + empty states

---

### Milestone 7 — GATE Scanner Page Redesign
**Scope:** Frontend — `/scanner` page.
- Scan controls: mode selector, Run Scan button, progress bar
- Real-time streaming results via WebSocket
- Filter tabs: BUY Opportunity / Watch / No Action
- Expandable rows: GATE components, targets, quality flags
- Business terminology chips throughout

---

### Milestone 8 — Watchlist & Paper Trading UI
**Scope:** Frontend — `/watchlist` and `/paper-trading` pages.
- Watchlist: auto-managed view, status chips, history timeline
- Paper Trading: performance summary, live positions with P&L, trade history, manual sell override

---

### Milestone 9 — Master Stocks & Backtest Polish
**Scope:** Frontend — `/stocks` and `/backtest` pages.
- Stocks: add signal status + last scanned columns; step-progress sync modal
- Backtest: move to `/backtest`, add 5 stat cards, equity curve chart

---

### Milestone 10 — UI/UX Polish & Production Readiness
**Scope:** Frontend + minor backend.
- Loading skeletons on every page
- Toast notifications for every user action
- Empty state screens throughout
- Consistent color system + theme
- Error boundaries per page
- Backend: `GET /api/health/detailed`
