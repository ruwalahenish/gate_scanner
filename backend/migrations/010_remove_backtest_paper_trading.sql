-- ============================================================
-- Migration 010 — Remove Backtesting & Paper Trading
-- Paper Trading and Backtesting have been permanently discontinued.
-- Drops every table that backed either feature, in FK-safe order
-- (children before parents). CASCADE is included as a safety net
-- for any dependent index/constraint; no other live table (scans,
-- signals, watchlist, alerts, stock_master, scan_metrics) references
-- any of these, so nothing else is affected.
--
-- WARNING: this permanently deletes all paper-trade and backtest
-- history. Confirm before running.
--
-- Run: psql $DATABASE_URL -f backend/migrations/010_remove_backtest_paper_trading.sql
-- Safe to re-run (all statements use IF EXISTS).
-- ============================================================

-- ── Backtesting ──────────────────────────────────────────────
DROP TABLE IF EXISTS backtest_stock_results CASCADE;
DROP TABLE IF EXISTS backtest_equity_curve CASCADE;
DROP TABLE IF EXISTS backtest_trades CASCADE;
DROP TABLE IF EXISTS backtests CASCADE;

-- ── Paper Trading ────────────────────────────────────────────
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS positions CASCADE;
DROP TABLE IF EXISTS portfolio_config CASCADE;
