export interface PaperTradingSummary {
  initial_capital: number;
  current_capital: number;
  invested_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
  total_pnl_pct: number;
  open_positions: number;
  total_trades: number;
  winning_trades: number;
  win_rate: number;
}

export interface PaperTradingPerformance extends PaperTradingSummary {
  losing_trades: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  best_trade_pct: number;
  worst_trade_pct: number;
}

export interface Position {
  id: string;
  symbol: string;
  side: "BUY";
  quantity: number;
  avg_entry: number;
  stop_loss: number | null;
  t1: number | null;
  t2: number | null;
  t3: number | null;
  trailing_sl: number | null;
  current_sl_level: string;
  signal_id: string | null;
  opened_at: string;
  status: "open" | "partially_closed" | "closed";
  notes: string | null;
  auto_created: boolean;
  creation_source: "manual" | "scanner_auto";
  // Live-enriched fields
  current_price?: number | null;
  unrealized_pnl?: number | null;
  unrealized_pnl_pct?: number | null;
}

export interface Trade {
  id: string;
  position_id: string | null;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  executed_at: string;
  exit_reason: string | null;
  pnl_abs: number | null;
  pnl_pct: number | null;
  notes: string | null;
}
