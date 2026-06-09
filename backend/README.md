---
title: gate-backend
sdk: docker
app_port: 10000
pinned: true
---

# GATE Scanner — Backend

FastAPI + Celery backend for the GATE Trading Intelligence platform.

## Environment Variables (set in Space Settings → Variables and secrets)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | NeonDB pooled connection string |
| `REDIS_URL` | Yes | Upstash Redis URL (`rediss://...`) |
| `ALLOWED_ORIGINS` | Yes | JSON array: `["https://your-app.vercel.app"]` |
| `INTERNAL_SECRET` | Yes | Bearer token for cron-job.org task triggers |
| `GATE_CACHE_DIR` | No | Defaults to `/tmp/.gate_cache` |
| `SCAN_EXECUTOR_WORKERS` | No | Defaults to `1` (suitable for HF free CPU) |
| `TELEGRAM_BOT_TOKEN` | No | Leave empty to disable Telegram alerts |
| `TELEGRAM_CHAT_ID` | No | Leave empty to disable Telegram alerts |

## Scheduled Tasks

Celery Beat is replaced by [cron-job.org](https://cron-job.org) HTTP triggers.
Configure 5 jobs in cron-job.org pointing to this Space's endpoints:

| Endpoint | Schedule (UTC) | IST equivalent |
|---|---|---|
| `POST /api/internal/tasks/daily-scan` | `35 10 * * 1-5` | 16:05 Mon–Fri |
| `POST /api/internal/tasks/stock-sync` | `30 0 * * 0` | 06:00 Sunday |
| `POST /api/internal/tasks/fundamentals` | `*/15 * * * *` | every 15 min |
| `POST /api/internal/tasks/monitor-trades` | `*/5 9-16 * * 1-5` | every 5 min market hours |
| `POST /api/internal/tasks/broadcast-prices` | `*/5 9-16 * * 1-5` | every 5 min market hours |

Each request must include the header: `Authorization: Bearer <INTERNAL_SECRET>`
