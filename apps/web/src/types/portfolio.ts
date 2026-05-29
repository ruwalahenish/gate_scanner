export interface Position {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
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
  status: "open" | "partially_closed";
  notes: string | null;
  current_price?: number;
  unrealized_pnl?: number;
  unrealized_pnl_pct?: number;
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

export interface PortfolioSummary {
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

export interface BuyRequest {
  symbol: string;
  quantity: number;
  price: number;
  signal_id?: string;
  stop_loss?: number;
  t1?: number;
  t2?: number;
  t3?: number;
  notes?: string;
}

export interface SellRequest {
  position_id: string;
  quantity: number;
  price: number;
  exit_reason?: string;
  notes?: string;
}
