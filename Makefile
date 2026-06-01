# ─────────────────────────────────────────────────────────
# GATE Trading Intelligence Platform — Developer Commands
# Usage: make <target>
# ─────────────────────────────────────────────────────────

.PHONY: help dev up down logs db-migrate backend frontend install clean

help:
	@echo ""
	@echo "  make dev         ★ Start everything in one terminal (recommended)"
	@echo "  make up          Start all services (Docker)"
	@echo "  make down        Stop all services"
	@echo "  make logs        Tail logs for api + worker"
	@echo "  make db-migrate  Run SQL migration against NeonDB"
	@echo "  make backend     Run FastAPI locally (no Docker)"
	@echo "  make worker      Run Celery worker locally"
	@echo "  make frontend    Run Next.js dev server"
	@echo "  make install     Install all dependencies"
	@echo "  make clean       Remove __pycache__ and .next"
	@echo ""

# ── All-in-one dev launcher ──────────────────────────────
dev:
	python dev.py

# ── Docker ───────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f api worker

# ── Database ─────────────────────────────────────────────
db-migrate:
	psql $$DATABASE_URL -f backend/migrations/001_initial_schema.sql

# ── Local Development ────────────────────────────────────
backend:
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	cd backend && celery -A app.tasks.celery_app worker --loglevel=info --pool=solo

beat:
	cd backend && celery -A app.tasks.celery_app beat --loglevel=info

frontend:
	cd apps/web && npm run dev

install:
	pip install -r backend/requirements.txt
	cd apps/web && npm install

# ── Scanner (runs through backend service layer) ──────────────────────
scan:
	cd backend && python -c "from app.core.scanner.pipeline import run_scan; run_scan()"

scan-daily:
	cd backend && python -c "from app.core.scanner.pipeline import run_daily_scan; run_daily_scan()"

# ── Cleanup ──────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .next -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
