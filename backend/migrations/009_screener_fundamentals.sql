-- Migration 009: Extended fundamental columns sourced from Screener.in
-- Safe to run on a live database — all statements use ADD COLUMN IF NOT EXISTS.

ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS roce_actual              NUMERIC(8,4);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS opm_latest               NUMERIC(8,4);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS free_cash_flow           BIGINT;
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS promoter_holding         NUMERIC(6,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS fii_holding              NUMERIC(6,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS dii_holding              NUMERIC(6,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS debtor_days              NUMERIC(8,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS revenue_cagr_3y          NUMERIC(8,4);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS profit_cagr_3y           NUMERIC(8,4);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS screener_price           NUMERIC(12,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS screener_52w_high        NUMERIC(12,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS screener_52w_low         NUMERIC(12,2);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS screener_price_change_pct NUMERIC(8,4);
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS screener_price_updated_at TIMESTAMPTZ;
ALTER TABLE stock_master ADD COLUMN IF NOT EXISTS data_source              VARCHAR(20) DEFAULT 'yfinance';
