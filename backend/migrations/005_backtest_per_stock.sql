-- Migration 005: Per-symbol backtest support
-- Adds Celery task_id (for cancellation), scope (portfolio vs symbol run),
-- and investment_per_stock (fixed ₹ budget per trade for single-stock runs).

ALTER TABLE backtests
  ADD COLUMN IF NOT EXISTS task_id              VARCHAR(255),
  ADD COLUMN IF NOT EXISTS scope               VARCHAR(20) DEFAULT 'portfolio',
  ADD COLUMN IF NOT EXISTS investment_per_stock NUMERIC(14,2);
