-- ============================================================
-- GATE Trading Intelligence Platform — Strategy Engine Rework
-- Migration 008
-- Run: psql $DATABASE_URL -f backend/migrations/008_strategy_rework.sql
--
-- Adds:
--   1) Extended fundamentals on stock_master (ROE/ROCE, growth, debt, margin)
--   2) Breakout/range + new-score columns on signals (consolidation-range
--      strategy model: where price sits vs its breakout zone)
--
-- All statements are idempotent (ADD COLUMN IF NOT EXISTS) — safe on a live DB.
-- ============================================================

-- ----------------------------------------------------------------
-- 1) stock_master: extended fundamentals (yfinance .info)
--    ROCE is not directly exposed by yfinance — approximated from
--    returnOnAssets where present, else left NULL. Documented limitation.
-- ----------------------------------------------------------------
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS roe             NUMERIC(8,4);  -- returnOnEquity (fraction)
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS roce            NUMERIC(8,4);  -- approx via returnOnAssets
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS revenue_growth  NUMERIC(8,4);  -- revenueGrowth (fraction)
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS profit_growth   NUMERIC(8,4);  -- earnings(Quarterly)Growth (fraction)
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS debt_to_equity  NUMERIC(10,2); -- debtToEquity (yfinance reports as %)
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS profit_margin   NUMERIC(8,4);  -- profitMargins (fraction)

-- ----------------------------------------------------------------
-- 2) signals: consolidation-range / breakout-state model + new scores
-- ----------------------------------------------------------------
ALTER TABLE signals ADD COLUMN IF NOT EXISTS breakout_state    VARCHAR(20);   -- BUY_ZONE | BREAKOUT_CONFIRMED | ACCUMULATION | EXTENDED | BROKEN_DOWN | NO_GATE
ALTER TABLE signals ADD COLUMN IF NOT EXISTS range_high        NUMERIC(12,2); -- consolidation box top (breakout resistance)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS range_low         NUMERIC(12,2); -- consolidation box bottom (support)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS breakout_level    NUMERIC(12,2); -- trigger price just above range_high
ALTER TABLE signals ADD COLUMN IF NOT EXISTS measured_move     NUMERIC(12,2); -- T1 = breakout_level + box height
ALTER TABLE signals ADD COLUMN IF NOT EXISTS rs_score          NUMERIC(6,2);  -- relative strength vs Nifty (0-100)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS sector_momentum   NUMERIC(6,2);  -- sector momentum (0-100)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS accumulation_score NUMERIC(6,2); -- volume-based smart-money proxy (0-100)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS fundamental_score NUMERIC(6,2);  -- fundamental quality (0-100)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS volume_buildup    BOOLEAN;       -- dry-up-then-expansion pattern present

-- Fast filtering by breakout state (only the actionable states matter)
CREATE INDEX IF NOT EXISTS idx_signals_breakout_state ON signals(breakout_state);
