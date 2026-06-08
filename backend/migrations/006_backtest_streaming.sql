-- Per-stock streaming results: populated incrementally as each batch completes
CREATE TABLE IF NOT EXISTS backtest_stock_results (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    backtest_id      UUID NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    symbol           VARCHAR(20)  NOT NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'done',   -- done | failed
    total_trades     INT          NOT NULL DEFAULT 0,
    winning_trades   INT          NOT NULL DEFAULT 0,
    win_rate         NUMERIC(5,2),
    total_pnl_abs    NUMERIC(14,2),
    avg_pnl_pct      NUMERIC(10,4),
    best_trade_pct   NUMERIC(10,4),
    worst_trade_pct  NUMERIC(10,4),
    avg_holding_days NUMERIC(8,2),
    category         VARCHAR(30),
    error_message    TEXT,
    completed_at     TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (backtest_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_bsr_backtest_id ON backtest_stock_results(backtest_id);

-- Progress tracking: how many symbols have been scanned so far
ALTER TABLE backtests
  ADD COLUMN IF NOT EXISTS total_symbols   INT,
  ADD COLUMN IF NOT EXISTS scanned_symbols INT DEFAULT 0;
