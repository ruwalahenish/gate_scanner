# GATE Scanner — Full Deployment Guide 

> **Cost: $0/month · No credit card required anywhere**
>
> Stack: HuggingFace Spaces (backend) · Vercel (frontend) · NeonDB (database) · Upstash Redis · cron-job.org (scheduler) · UptimeRobot (monitoring)

---

## Table of Contents

1. [Prerequisites & Overview](#1-prerequisites--overview)
2. [NeonDB — PostgreSQL Database](#2-neondb--postgresql-database)
3. [Upstash — Redis Broker](#3-upstash--redis-broker)
4. [HuggingFace Spaces — Backend API](#4-huggingface-spaces--backend-api)
5. [Vercel — Frontend](#5-vercel--frontend)
6. [GitHub Actions — CI/CD Pipeline](#6-github-actions--cicd-pipeline)
7. [cron-job.org — Scheduled Tasks](#7-cron-joborg--scheduled-tasks)
8. [UptimeRobot — Monitoring & Alerts](#8-uptimerobot--monitoring--alerts)
9. [End-to-End Verification](#9-end-to-end-verification)
10. [Troubleshooting](#10-troubleshooting)
11. [Upgrade Path](#11-upgrade-path)

---

## 1. Prerequisites & Overview

### What Gets Deployed Where

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Repository (monorepo)                                   │
│    backend/   ──push──►  HuggingFace Space  (FastAPI + Celery)  │
│    apps/web/  ──deploy►  Vercel             (Next.js frontend)  │
└─────────────────────────────────────────────────────────────────┘

External services:
  NeonDB          PostgreSQL 16, free tier, no CC
  Upstash Redis   Redis 7, free tier, no CC
  cron-job.org    HTTP cron scheduler, replaces Celery Beat
  UptimeRobot     Health monitoring + Telegram alerts
```

### How Scheduled Tasks Work (no Celery Beat)

Celery Beat was removed from the container. Instead, **cron-job.org** makes authenticated HTTP POST requests to `/api/internal/tasks/*` endpoints on a schedule. Each call:
1. Wakes the HuggingFace Space if it was sleeping
2. Queues the task in the Celery worker

During Indian market hours (9:00–16:15 IST), the 5-minute pings keep the Space awake continuously. Outside market hours, the Space may sleep — that is expected and acceptable.

### What You Need Before Starting

- A GitHub account (repo already pushed)
- An email address (for HuggingFace, NeonDB, Upstash, cron-job.org, UptimeRobot)
- Your own domain (optional — free `*.hf.space` and `*.vercel.app` subdomains work fine)
- `psql` installed locally **or** use the NeonDB web SQL editor (no install needed)

### Time Estimate

| Section | Time |
|---|---|
| NeonDB setup + migrations | 15 min |
| Upstash Redis | 5 min |
| HuggingFace Space | 10 min |
| Vercel | 10 min |
| GitHub Actions secrets | 5 min |
| cron-job.org (5 jobs) | 10 min |
| UptimeRobot | 5 min |
| First deploy + verification | 15 min |
| **Total** | **~75 min** |

---

## 2. NeonDB — PostgreSQL Database

**URL:** https://console.neon.tech  
**Free tier:** 0.5 GB storage, 100 CU-hours/month — no credit card

### 2.1 Create Account

1. Go to https://console.neon.tech
2. Click **Sign Up** → choose **Continue with GitHub**
3. Authorize the GitHub OAuth app
4. You are now on the Neon dashboard

### 2.2 Create a Project

1. Click **New Project**
2. Fill in:
   - **Project name:** `gate-platform`
   - **Database name:** `gate_platform`
   - **Region:** Choose the closest to you (e.g., `AWS / ap-southeast-1` for India/Asia)
   - **PostgreSQL version:** 16
3. Click **Create project**
4. A credentials popup appears — **do not close it yet**

### 2.3 Copy the Connection String

In the credentials popup:
1. Click the **Pooled connection** tab (this uses PgBouncer — required for asyncpg)
2. Copy the connection string. It looks like:
   ```
   postgresql://gate_platform_owner:XXXXXXXX@ep-xxx-yyy.ap-southeast-1.aws.neon.tech/gate_platform?sslmode=require
   ```
3. Save this as `DATABASE_URL` — you will need it in multiple places

> **Important:** Use the **Pooled** string, not the direct connection. The backend's asyncpg pool has `statement_cache_size=0` which is required for NeonDB's PgBouncer.

### 2.4 Run Database Migrations

You have two options. Use whichever is easier.

#### Option A: NeonDB SQL Editor (no installation needed)

1. In Neon dashboard → click your project → **SQL Editor** in the left sidebar
2. For each file below, click **New query**, paste the entire file contents, click **Run**:
   - `backend/migrations/001_initial_schema.sql`
   - `backend/migrations/002_stock_master.sql`
   - `backend/migrations/003_performance_indexes.sql`
   - `backend/migrations/004_architecture_v2.sql`
   - `backend/migrations/005_backtest_per_stock.sql`
   - `backend/migrations/006_backtest_streaming.sql`
3. Run them **in order** — each one depends on the previous

#### Option B: psql command line

```bash
# Set your connection string
export DATABASE_URL="postgresql://gate_platform_owner:PASS@ep-xxx.neon.tech/gate_platform?sslmode=require"

# Run all migrations in order
psql "$DATABASE_URL" -f backend/migrations/001_initial_schema.sql
psql "$DATABASE_URL" -f backend/migrations/002_stock_master.sql
psql "$DATABASE_URL" -f backend/migrations/003_performance_indexes.sql
psql "$DATABASE_URL" -f backend/migrations/004_architecture_v2.sql
psql "$DATABASE_URL" -f backend/migrations/005_backtest_per_stock.sql
psql "$DATABASE_URL" -f backend/migrations/006_backtest_streaming.sql
```

### 2.5 Verify Tables Exist

In the SQL Editor, run:

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected output includes: `scans`, `signals`, `positions`, `trades`, `watchlist_items`, `stock_master`, `backtests`, `backtest_stock_results`, and others.

---

## 3. Upstash — Redis Broker

**URL:** https://console.upstash.com  
**Free tier:** 500 K commands/month — no credit card

### 3.1 Create Account

1. Go to https://console.upstash.com
2. Click **Sign Up** → choose **Continue with GitHub**
3. Authorize the app → you are on the Upstash console

### 3.2 Create a Redis Database

1. Click **Create Database**
2. Fill in:
   - **Name:** `gate-redis`
   - **Type:** Regional
   - **Region:** Choose the one closest to HuggingFace's EU infrastructure. Recommended: **EU-West-1 (Ireland)** or **US-East-1** — HF Spaces typically runs in EU
   - **Eviction:** Leave as **No eviction** (or **allkeys-lru** if you want auto-cleanup on memory pressure)
3. Click **Create**

### 3.3 Copy the Redis URL

1. On the database page, scroll to **REST API** section
2. Find the **Redis URL** field. It looks like:
   ```
   rediss://default:XXXXXXXXXXXXXXXXXXXXXXXX@global-apt-xxxxx-12345.upstash.io:6379
   ```
3. Note the `rediss://` prefix (double-s = TLS) — this is required

> Save this as `REDIS_URL`. The Python `redis` library supports TLS natively with the `rediss://` scheme.

### 3.4 Verify Connection (optional)

In the Upstash console, click **CLI** tab and run:
```
PING
```
Expected response: `PONG`

---

## 4. HuggingFace Spaces — Backend API

**URL:** https://huggingface.co  
**Free tier:** CPU Basic (2 vCPU, 16 GB RAM) — no credit card

### 4.1 Create HuggingFace Account

1. Go to https://huggingface.co
2. Click **Sign Up** (top right)
3. Enter your email, set a password, choose a username
4. Verify your email
5. Note your **username** — you will need it in multiple places. Your Space URL will be:
   ```
   https://YOUR_USERNAME-gate-backend.hf.space
   ```

### 4.2 Generate an Access Token

1. Click your profile avatar (top right) → **Settings**
2. Click **Access Tokens** in the left sidebar
3. Click **New token**
4. Fill in:
   - **Name:** `github-actions-deploy`
   - **Type:** **Write** (required to push code to the Space)
5. Click **Generate a token**
6. **Copy the token immediately** — it will not be shown again
7. Save as `HF_TOKEN`

### 4.3 Create the Docker Space

1. Click **+** (top right) → **New Space** (or go to https://huggingface.co/new-space)
2. Fill in:
   - **Space name:** `gate-backend`
   - **License:** MIT (or choose any)
   - **SDK:** **Docker**
   - **Docker template:** Blank
   - **Hardware:** CPU Basic · Free (already selected)
   - **Visibility:** **Private**
3. Click **Create Space**
4. You land on an empty Space page — this is correct. GitHub Actions will push the code.

### 4.4 Set Environment Variables (Space Secrets)

1. On your Space page, click the **Settings** tab
2. Scroll to **Variables and secrets** section
3. Add each variable below. For secrets (marked **Secret**), click **Add secret** — these are encrypted and hidden in logs. For plain variables, click **Add variable**.

| Variable | Value | Type |
|---|---|---|
| `DATABASE_URL` | Your NeonDB pooled connection string from Step 2.3 | **Secret** |
| `REDIS_URL` | Your Upstash Redis URL from Step 3.3 | **Secret** |
| `ALLOWED_ORIGINS` | `["https://YOUR-APP.vercel.app"]` — update after Vercel deploy | **Secret** |
| `INTERNAL_SECRET` | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` | **Secret** |
| `GATE_CACHE_DIR` | `/tmp/.gate_cache` | Variable |
| `SCAN_EXECUTOR_WORKERS` | `1` | Variable |
| `TELEGRAM_BOT_TOKEN` | Your bot token (or leave empty to disable alerts) | **Secret** |
| `TELEGRAM_CHAT_ID` | Your chat ID (or leave empty) | **Secret** |

> **Save your `INTERNAL_SECRET` value** — you will need to enter it again in cron-job.org (Step 7).

### 4.5 Understand the Space URL

Your backend will be accessible at:
```
https://YOUR_USERNAME-gate-backend.hf.space
```

WebSocket connections use:
```
wss://YOUR_USERNAME-gate-backend.hf.space/ws
```

The format is always: `https://USERNAME-SPACE_NAME.hf.space`

> The Space won't show anything yet — code is pushed via GitHub Actions in Step 6.

---

## 5. Vercel — Frontend

**URL:** https://vercel.com  
**Free tier:** Hobby plan — no credit card

### 5.1 Create Vercel Account

1. Go to https://vercel.com
2. Click **Sign Up** → choose **Continue with GitHub**
3. Authorize the OAuth app

### 5.2 Import the Project

1. Click **Add New** → **Project**
2. Find your GitHub repository in the list → click **Import**
3. Configure the project:

   **Framework Preset:** Next.js ← should auto-detect

   **Root Directory:** Click **Edit** → type `apps/web` → click **Continue**

   > This is the critical step for monorepo deployment. Without setting root directory to `apps/web`, Vercel will try to build from the repo root and fail.

4. Expand **Environment Variables** and add:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://YOUR_HF_USERNAME-gate-backend.hf.space` |
   | `NEXT_PUBLIC_WS_URL` | `wss://YOUR_HF_USERNAME-gate-backend.hf.space/ws` |

   Replace `YOUR_HF_USERNAME` with your actual HuggingFace username.

5. Click **Deploy**

### 5.3 Note Your Production URL

After deployment (1–2 minutes):
1. Vercel shows a success screen with your URL: `https://gate-scanner-xxx.vercel.app` (or a custom name)
2. Copy this URL

### 5.4 Update CORS on HuggingFace Space

Now that you have the Vercel URL:
1. Go back to your HF Space → **Settings** → **Variables and secrets**
2. Edit `ALLOWED_ORIGINS` → set the value to:
   ```
   ["https://YOUR-APP.vercel.app"]
   ```
   Replace `YOUR-APP` with your actual Vercel subdomain.
3. Click **Save** — the Space rebuilds automatically (takes ~3 minutes)

### 5.5 Get Vercel Project IDs (for GitHub Actions)

1. Go to Vercel dashboard → your project → **Settings** → **General**
2. Scroll down to find **Project ID** — copy it. Save as `VERCEL_PROJECT_ID`
3. Go to Vercel dashboard → your team/account → **Settings** (top nav)
4. Find **Team ID** (or personal account ID) — copy it. Save as `VERCEL_ORG_ID`

Alternatively, run locally in `apps/web/`:
```bash
npx vercel link
# Follow prompts — links to your project
cat .vercel/project.json
# Shows: {"projectId":"xxx","orgId":"yyy"}
```

---

## 6. GitHub Actions — CI/CD Pipeline

GitHub Actions automatically runs CI checks and deploys when you push to `main`. No credit card needed.

### 6.1 Add Repository Secrets

Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add each of these secrets:

| Secret Name | Value | Where to Get It |
|---|---|---|
| `HF_TOKEN` | Your HuggingFace access token | Step 4.2 |
| `HF_USERNAME` | Your HuggingFace username (e.g., `johndoe`) | Your HF profile |
| `VERCEL_TOKEN` | Create at: Vercel → Settings → Tokens → **Create** | Vercel dashboard |
| `VERCEL_ORG_ID` | The Team ID or personal account ID | Step 5.5 |
| `VERCEL_PROJECT_ID` | The Vercel project ID | Step 5.5 |

### 6.2 Update Placeholder URLs in the Workflow

Open [.github/workflows/ci.yml](.github/workflows/ci.yml) and find the `frontend` job's build step:

```yaml
      - name: Build
        env:
          NEXT_PUBLIC_API_URL: "https://YOUR_HF_USERNAME-gate-backend.hf.space"
          NEXT_PUBLIC_WS_URL: "wss://YOUR_HF_USERNAME-gate-backend.hf.space/ws"
```

Replace `YOUR_HF_USERNAME` with your actual HuggingFace username. Example:
```yaml
          NEXT_PUBLIC_API_URL: "https://johndoe-gate-backend.hf.space"
          NEXT_PUBLIC_WS_URL: "wss://johndoe-gate-backend.hf.space/ws"
```

Commit and push this change.

### 6.3 Understand How Deploys Work

The workflow is path-filtered:

| What changed | Jobs that run |
|---|---|
| `backend/**` | Backend CI → Docker smoke test → Deploy to HF Space |
| `apps/web/**` | Frontend CI → Deploy to Vercel |
| Both | All jobs |
| Neither (e.g., docs) | Only the `changes` detection job |

**Backend deploy mechanism:**
1. GitHub Actions clones your HF Space git repo
2. Copies all files from `backend/` into the Space repo
3. Commits and pushes — HF Spaces detects the push and rebuilds the Docker image
4. Rebuild takes 3–8 minutes on first push (pandas/numpy compile), ~2 min on subsequent pushes

**Frontend deploy mechanism:**
1. Vercel CLI builds the Next.js app
2. Deploys to Vercel's CDN
3. On `main` branch → production URL updated
4. On other branches → preview URL created and commented on the PR

### 6.4 Trigger the First Backend Deploy

Push the placeholder URL change from Step 6.2:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: set HuggingFace Space URLs"
git push origin main
```

Watch the Actions tab in GitHub. The `deploy-backend` job will:
1. Clone HF Space repo
2. `rsync` backend files into it
3. Push to HF — you will see the Space start rebuilding at https://huggingface.co/spaces/YOUR_USERNAME/gate-backend

### 6.5 Watch the First Build

On your HF Space page:
1. Click the **App** tab — you will see build logs streaming
2. First build takes 5–10 minutes (installs pandas, numpy, pyarrow)
3. Subsequent builds take 2–3 minutes (Docker layer cache)
4. When the build finishes, the App tab shows the running service

---

## 7. cron-job.org — Scheduled Tasks

**URL:** https://cron-job.org  
**Free tier:** Unlimited jobs, 1-minute minimum interval — no credit card

Cron-job.org replaces Celery Beat. It calls authenticated HTTP POST endpoints on your HF Space to trigger each scheduled task.

### 7.1 Create Account

1. Go to https://cron-job.org
2. Click **Register**
3. Enter your email and password — no credit card required
4. Verify your email

### 7.2 Create the 5 Scheduled Jobs

For each job below:
1. Click **CREATE CRONJOB** (top right)
2. Fill in the fields as described in the table
3. Click **CREATE**

---

#### Job 1: Daily Post-Market Scan

| Field | Value |
|---|---|
| **Title** | `GATE Daily Scan` |
| **URL** | `https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/daily-scan` |
| **Request method** | `POST` |
| **Schedule** | Custom cron: `35 10 * * 1-5` |
| **Headers** | Key: `Authorization` · Value: `Bearer YOUR_INTERNAL_SECRET` |

> `35 10 * * 1-5` = 10:35 UTC = 16:05 IST, Monday–Friday

---

#### Job 2: Weekly Stock Master Sync

| Field | Value |
|---|---|
| **Title** | `GATE Stock Sync` |
| **URL** | `https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/stock-sync` |
| **Request method** | `POST` |
| **Schedule** | Custom cron: `30 0 * * 0` |
| **Headers** | Key: `Authorization` · Value: `Bearer YOUR_INTERNAL_SECRET` |

> `30 0 * * 0` = 00:30 UTC Sunday = 06:00 IST Sunday

---

#### Job 3: Fundamentals Enrichment (every 15 min)

| Field | Value |
|---|---|
| **Title** | `GATE Fundamentals` |
| **URL** | `https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/fundamentals` |
| **Request method** | `POST` |
| **Schedule** | Custom cron: `*/15 * * * *` |
| **Headers** | Key: `Authorization` · Value: `Bearer YOUR_INTERNAL_SECRET` |

> Runs every 15 minutes, 24/7. These calls during off-hours do nothing meaningful but each call's latency is ~100ms and cron-job.org handles this fine on the free tier.

---

#### Job 4: Paper Trade Monitor (every 5 min, market hours)

| Field | Value |
|---|---|
| **Title** | `GATE Trade Monitor` |
| **URL** | `https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/monitor-trades` |
| **Request method** | `POST` |
| **Schedule** | Custom cron: `*/5 3-10 * * 1-5` |
| **Headers** | Key: `Authorization` · Value: `Bearer YOUR_INTERNAL_SECRET` |

> `3-10 UTC` = `8:30–16:30 IST` — covers the full NSE trading session (9:15–15:30 IST) with buffer. Runs Monday–Friday only.

> **This job also keeps the Space awake during market hours.** Each ping resets the 48-hour inactivity timer, so the Space never sleeps on trading days.

---

#### Job 5: Price Broadcast (every 5 min, market hours)

| Field | Value |
|---|---|
| **Title** | `GATE Price Broadcast` |
| **URL** | `https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/broadcast-prices` |
| **Request method** | `POST` |
| **Schedule** | Custom cron: `2-59/5 3-10 * * 1-5` |
| **Headers** | Key: `Authorization` · Value: `Bearer YOUR_INTERNAL_SECRET` |

> Offset by 2 minutes from Job 4 so jobs don't fire at the exact same second. `2-59/5` = minute 2, 7, 12, 17, ... 57

### 7.3 How to Set Headers in cron-job.org

When creating a job, in the **Advanced** tab (or **Headers** section depending on the UI version):
1. Click **Add Header**
2. **Header name:** `Authorization`
3. **Header value:** `Bearer YOUR_INTERNAL_SECRET`

Replace `YOUR_INTERNAL_SECRET` with the value you generated in Step 4.4 (the 64-character hex string).

### 7.4 Verify a Job Manually

1. In cron-job.org, open one of your jobs
2. Click **Run now** (or **Test**)
3. Expected HTTP response: `200 OK` with body `{"queued":"..."}`
4. If you get `403 Forbidden`: the Authorization header is wrong — check the token value
5. If you get a timeout: the Space is sleeping — wait 60 seconds and try again

---

## 8. UptimeRobot — Monitoring & Alerts

**URL:** https://uptimerobot.com  
**Free tier:** 50 monitors, 5-minute check interval — no credit card

### 8.1 Create Account

1. Go to https://uptimerobot.com
2. Click **Register for FREE**
3. Enter your email and create a password
4. Verify your email

### 8.2 Add Alert Contact (Telegram)

If you want alerts on your phone via the Telegram bot used by the app:

1. Dashboard → **My Settings** → **Alert Contacts** → **Add Alert Contact**
2. Choose **Telegram**
3. Enter your `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
4. Click **Send Test Alert** — verify you receive a message
5. Save the contact

If you prefer email alerts, skip this step — UptimeRobot sends email alerts by default.

### 8.3 Add Backend Monitor

1. Dashboard → **Add New Monitor**
2. Fill in:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** `GATE Backend`
   - **URL:** `https://YOUR_USERNAME-gate-backend.hf.space/api/health`
   - **Monitoring Interval:** 5 minutes
3. Under **Alert Contacts**, select your Telegram or email contact
4. Click **Create Monitor**

### 8.4 Add Frontend Monitor

1. Click **Add New Monitor** again
2. Fill in:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** `GATE Frontend`
   - **URL:** `https://YOUR-APP.vercel.app`
   - **Monitoring Interval:** 5 minutes
3. Select the same alert contact
4. Click **Create Monitor**

### 8.5 Understanding Alerts

UptimeRobot pings `/api/health` every 5 minutes. If the HF Space is sleeping, the health check wakes it. You may receive a brief "DOWN" alert when the Space is first waking up (~30–60 seconds). This is normal after a weekend/holiday period. Configure a **tolerance** of 2 failed checks before alerting (in monitor settings) to avoid false alarms.

---

## 9. End-to-End Verification

Run these checks after all steps are complete.

### 9.1 Backend Health

```bash
# Simple health check
curl https://YOUR_USERNAME-gate-backend.hf.space/api/health

# Expected:
# {"ok":true,"service":"gate-trading-api","version":"1.0.0"}
```

```bash
# Detailed health — verifies DB and Redis connectivity
curl https://YOUR_USERNAME-gate-backend.hf.space/api/health/detailed

# Expected (all true):
# {"db_ok":true,"redis_ok":true,"db_pool_size":2,...}
```

### 9.2 Internal Endpoints (verifies cron-job.org setup)

```bash
# Test fundamentals trigger (safe to run any time)
curl -X POST https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/fundamentals \
  -H "Authorization: Bearer YOUR_INTERNAL_SECRET" \
  -H "Content-Type: application/json"

# Expected:
# {"queued":"fundamentals"}

# Test with wrong token (should return 403)
curl -X POST https://YOUR_USERNAME-gate-backend.hf.space/api/internal/tasks/fundamentals \
  -H "Authorization: Bearer wrongtoken"

# Expected:
# {"detail":"Invalid token"}
```

### 9.3 Frontend Connectivity

1. Open `https://YOUR-APP.vercel.app` in Chrome
2. Open **DevTools** (F12) → **Network** tab → filter by **WS**
3. Reload the page
4. You should see a WebSocket connection to `wss://YOUR_USERNAME-gate-backend.hf.space/ws` with status `101 Switching Protocols`
5. Open **Console** tab — there should be **no CORS errors**

### 9.4 Trigger a Manual Scan

```bash
curl -X POST https://YOUR_USERNAME-gate-backend.hf.space/api/scans/trigger \
  -H "Content-Type: application/json" \
  -d '{"universe": "nifty50", "mode": "standard"}'

# Expected:
# {"scan_id":"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx","status":"pending",...}
```

In the frontend, you should see the scan progress events streaming via WebSocket in real time.

### 9.5 Verify Prometheus Metrics

```bash
curl https://YOUR_USERNAME-gate-backend.hf.space/metrics | head -30

# Expected output starts with:
# # HELP gate_scan_duration_seconds ...
# # TYPE gate_scan_duration_seconds histogram
```

### 9.6 Verify cron-job.org Integration

1. Log into cron-job.org
2. Open the `GATE Trade Monitor` job
3. Click **Run now**
4. Check the **Execution log** — expect HTTP status `200` and response `{"queued":"monitor-trades"}`

### 9.7 Full Deployment Checklist

- [ ] `GET /api/health` returns `{"ok":true}`
- [ ] `GET /api/health/detailed` returns `db_ok:true` and `redis_ok:true`
- [ ] Frontend loads without errors at Vercel URL
- [ ] WebSocket connects (WS tab in DevTools shows 101)
- [ ] No CORS errors in browser console
- [ ] All 5 cron-job.org jobs show HTTP 200 in execution logs
- [ ] UptimeRobot shows both monitors as **Up**
- [ ] Triggering a scan shows progress in the frontend UI

---

## 10. Troubleshooting

### Backend shows "sleeping" / 30–60s first response

**Cause:** HF Space reached 48 hours of inactivity and entered sleep mode.  
**Fix:** Make a request to wake it. Subsequent requests are fast. During market hours, cron-job.org pings prevent sleep. On Monday mornings, the first cron ping at 08:30 UTC wakes the Space — expect the first market-hours tasks to be ~60s delayed.

### `db_ok: false` in health check

**Possible causes:**
1. `DATABASE_URL` env var not set in HF Space settings → double-check Step 4.4
2. Using the **direct** NeonDB URL instead of the **pooled** URL → go to NeonDB console, copy the pooled connection string
3. NeonDB free tier compute is paused (happens if unused for several days) → open the NeonDB console, the compute resumes automatically when you visit

### `redis_ok: false` in health check

**Possible causes:**
1. `REDIS_URL` not set in HF Space settings
2. Wrong URL format — must start with `rediss://` (double-s for TLS), not `redis://`
3. Upstash free tier limit exceeded (500K commands/month) → check Upstash console for usage

### `403 Forbidden` on internal endpoints

**Possible causes:**
1. `INTERNAL_SECRET` env var not set in HF Space settings
2. Mismatched token — the value in cron-job.org header must exactly match what is in HF Space `INTERNAL_SECRET`
3. Missing `Bearer ` prefix (with space) — header must be `Authorization: Bearer TOKEN`

### CORS errors in browser console

**Symptom:** Browser console shows `Access-Control-Allow-Origin` errors.  
**Fix:**
1. In HF Space settings, check `ALLOWED_ORIGINS` — it must contain your exact Vercel URL
2. Format must be a valid JSON array: `["https://your-app.vercel.app"]`
3. After updating `ALLOWED_ORIGINS`, restart the Space: Settings → Factory reboot (or just wait — HF restarts the Space when env vars change)

### GitHub Actions `deploy-backend` job fails

**Common errors:**

| Error | Fix |
|---|---|
| `Authentication failed` for HF git push | Check `HF_TOKEN` secret has **write** scope and is not expired |
| `Repository not found` | Check `HF_USERNAME` secret matches your HF username exactly (case-sensitive) |
| `rsync: command not found` | Add `sudo apt-get install -y rsync` step before the rsync command |
| `No space named gate-backend found` | Create the HF Space first (Step 4.3) before pushing via CI |

### HF Space build fails

1. Go to your Space → **App** tab → click **View build logs**
2. Common issue: `gcc` not found → the Dockerfile already installs it via `apt-get install -y gcc libpq-dev` — verify the Dockerfile wasn't accidentally modified
3. Out of disk space: HF Spaces free tier has limited disk. The Docker layer cache may fill up. Force a full rebuild: Space Settings → **Factory reboot**

### Vercel build fails

```
Error: NEXT_PUBLIC_API_URL is not defined
```
→ Add the env var in Vercel project settings (Step 5.2) and redeploy.

```
Type error: ...
```
→ Run `cd apps/web && npx tsc --noEmit` locally to see the error. Fix before pushing.

### Celery tasks not processing

The Celery worker runs inside the HF Space container. If tasks are being queued but not processed:
1. Check `GET /api/health/detailed` — if `redis_ok: false`, the worker can't connect to Redis and tasks queue up without being consumed
2. Check HF Space logs (App tab) for `[worker]` prefixed lines — worker startup errors appear here
3. Restart the Space: Settings → Factory reboot

---

## 11. Upgrade Path

If the free tier becomes insufficient for your usage:

### More CPU / no sleep risk

| Option | Platform | Monthly Cost | How |
|---|---|---|---|
| Always-on backend | Render Starter | $7 | Change `plan: free` → `plan: starter` in `render.yaml`, add Render Deploy Hook to CI |
| More CPU | HF Spaces CPU Upgrade | ~$0.05/hr | Change hardware in Space settings |
| Dedicated server | Hetzner CX22 (2 vCPU, 4GB) | ~€4 | Self-host with docker-compose |

### More Redis commands (Upstash)

Upstash free: 500K commands/month. If exceeded, add a payment method and pay-as-you-go rates apply (~$0.20 per 100K additional commands). For personal use, this is unlikely to exceed $1/month.

### Larger database (NeonDB)

NeonDB free: 0.5 GB storage. For personal trading use, this holds years of scan history. If needed, upgrade to the Launch plan ($19/month) for 10 GB.

### Adding Celery Beat back (for always-on platforms)

If you migrate to Render Starter or a self-hosted VPS, add Beat back to supervisord:

```ini
; Add this back to backend/supervisord.conf
[program:beat]
command=celery -A app.tasks.celery_app beat --loglevel=info --schedule /tmp/celerybeat-schedule
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
autorestart=true
startretries=3
priority=30
```

Also remove or disable the cron-job.org jobs to avoid double-firing tasks.

---

## Quick Reference

### All URLs (fill in after setup)

```
HF Space (Backend):   https://YOUR_HF_USERNAME-gate-backend.hf.space
WebSocket:            wss://YOUR_HF_USERNAME-gate-backend.hf.space/ws
Frontend:             https://YOUR-APP.vercel.app
API docs:             https://YOUR_HF_USERNAME-gate-backend.hf.space/api/docs
Prometheus metrics:   https://YOUR_HF_USERNAME-gate-backend.hf.space/metrics
Health check:         https://YOUR_HF_USERNAME-gate-backend.hf.space/api/health
Health detailed:      https://YOUR_HF_USERNAME-gate-backend.hf.space/api/health/detailed
```

### All GitHub Secrets Required

```
HF_TOKEN             HuggingFace write access token
HF_USERNAME          HuggingFace username
VERCEL_TOKEN         Vercel API token
VERCEL_ORG_ID        Vercel team/org ID
VERCEL_PROJECT_ID    Vercel project ID
```

### All HuggingFace Space Secrets Required

```
DATABASE_URL              NeonDB pooled connection string
REDIS_URL                 Upstash rediss:// URL
ALLOWED_ORIGINS           ["https://your-app.vercel.app"]
INTERNAL_SECRET           64-char hex secret for cron-job.org auth
TELEGRAM_BOT_TOKEN        Optional
TELEGRAM_CHAT_ID          Optional
```

### cron-job.org Schedule Reference (UTC)

```
Daily scan:     35 10 * * 1-5     → 16:05 IST Mon–Fri
Stock sync:     30 0 * * 0        → 06:00 IST Sunday
Fundamentals:   */15 * * * *      → every 15 min
Trade monitor:  */5 3-10 * * 1-5  → every 5 min, 08:30–16:30 IST weekdays
Price broadcast: 2-59/5 3-10 * * 1-5 → same window, offset by 2 min
```
