# GATE Trading Intelligence Platform — Quick Start

## Free Services Required

| Service | Free Tier | What It's Used For |
|---------|-----------|-------------------|
| [NeonDB](https://neon.tech) | 0.5 GB free forever | PostgreSQL database |
| [Upstash Redis](https://upstash.com) | 10k commands/day free | Cache + pub/sub (OR use local Docker Redis) |
| [Telegram Bot](https://t.me/BotFather) | Free | Mobile alert notifications |

---

## Step 1 — Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your NeonDB connection string:
# DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/gate_platform?sslmode=require

# If using local Docker Redis (recommended for development):
# REDIS_URL=redis://localhost:6379/0
```

## Step 2 — Create Database Schema

```bash
# Run migration against NeonDB
psql $DATABASE_URL -f backend/migrations/001_initial_schema.sql
```

## Step 3 — Set Up Frontend Environment

```bash
cd apps/web
cp .env.local.example .env.local
# .env.local already has correct localhost defaults for development
```

## Step 4 — Run with Docker Compose (Recommended)

```bash
# Start all services: Redis, FastAPI, Celery worker, Celery beat, Next.js
docker-compose up -d

# View logs
docker-compose logs -f api
docker-compose logs -f worker
```

## Step 5 — Run Locally (Development)

### Backend

```bash
cd backend

# Install dependencies (use existing venv or create new)
pip install -r requirements.txt

# Start FastAPI
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# In a second terminal — Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# In a third terminal — Celery beat (scheduled scans)
celery -A app.tasks.celery_app beat --loglevel=info
```

### Frontend

```bash
cd apps/web

# Install dependencies
npm install

# Start Next.js dev server
npm run dev
```

Open http://localhost:3000

---

## First Steps in the UI

1. **Dashboard** — Overview of portfolio, top signals, recent alerts
2. **Click "Run Scan"** in the top bar → triggers a post-market daily scan
3. **Signals tab** — Filter by category (INVESTMENT/SWING/POSITIONAL)
4. **Click a signal row** → expands detail with levels, analysis flags, reasoning
5. **Click symbol name** → Symbol detail page with TradingView chart
6. **Click "Paper Buy"** → fills position in virtual portfolio
7. **Portfolio tab** → track positions with real-time P&L
8. **Alerts tab** → create price alerts (e.g., RELIANCE price above ₹2500)

---

## Architecture at a Glance

```
apps/web/                       ← Next.js 15 frontend
  app/(dashboard)/              ← Route pages
  src/store/                    ← Redux Toolkit + RTK Query
  src/components/               ← MUI components

backend/                        ← FastAPI backend
  app/routers/                  ← REST API endpoints
  app/services/                 ← Engine adapter, alerts, WebSocket
  app/tasks/                    ← Celery scan/backtest jobs
  app/queries/                  ← Raw SQL (asyncpg, no ORM)
  migrations/                   ← SQL schema files

gate_scanner/                   ← UNCHANGED existing Python engines
  main.py, config.py, ...       ← All existing GATE logic preserved
```

---

## Telegram Alerts (Optional, Free)

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → get token
2. Get your chat ID from [@userinfobot](https://t.me/userinfobot)
3. Add to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```
4. Restart backend — price alerts will now also send Telegram messages

---

## Database Management

```sql
-- Check scan history
SELECT id, mode, status, signals_found, duration_sec, triggered_at
FROM scans ORDER BY triggered_at DESC LIMIT 10;

-- Check latest signals
SELECT symbol, category, rank_score, gate_strength, entry, t1, rr_t1
FROM signals
WHERE scan_id = (SELECT id FROM scans WHERE status='done' ORDER BY triggered_at DESC LIMIT 1)
ORDER BY rank_score DESC;

-- Reset portfolio to ₹10 lakhs
UPDATE portfolio_config SET initial_capital=1000000, current_capital=1000000;
DELETE FROM positions;
DELETE FROM trades;
```

---

## Deployment (Free VPS)

1. Get a free/cheap VPS: [Railway](https://railway.app) ($5/mo), [Render](https://render.com) (free tier), or DigitalOcean ($6/mo)
2. Point domain to VPS
3. Install nginx + certbot (free HTTPS)
4. Run `docker-compose up -d`
5. Apply `nginx.conf` to your nginx config

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `DB pool not initialised` | Check `DATABASE_URL` in `.env` |
| Scan never completes | Check Celery worker is running: `docker-compose logs worker` |
| WebSocket disconnects | Nginx timeout — apply the `nginx.conf` provided |
| No signals shown | Run a scan first via "Run Scan" button |
| `InsufficientCapitalError` | Portfolio capital exhausted — reset via SQL above |
