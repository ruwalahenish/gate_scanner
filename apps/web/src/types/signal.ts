export type SignalCategory = "INVESTMENT" | "SWING" | "POSITIONAL" | "WATCH" | "IGNORE";
export type SignalSide = "BUY" | "SELL";

export interface Signal {
  id: string;
  scan_id: string;
  symbol: string;
  category: SignalCategory;
  side: SignalSide | null;
  signal_timeframe: string | null;
  sl_timeframe: string | null;
  trend_direction: string | null;
  entry: number | null;
  stop_loss: number | null;
  sl_distance_pct: number | null;
  t1: number | null;
  t2: number | null;
  t3: number | null;
  rr_t1: number | null;
  rr_t2: number | null;
  rr_t3: number | null;
  gate_strength: number | null;
  volatility_compression: number | null;
  breakout_probability: number | null;
  confidence: number | null;
  rank_score: number | null;
  mtf_alignment_pct: number | null;
  structure_quality: number | null;
  atr: number | null;
  htf_confirmed: boolean | null;
  correction_validated: boolean | null;
  bounce_sequence_valid: boolean | null;
  fib_confluence: boolean | null;
  phase: string | null;
  trailing_plan: {
    on_T1_hit?: string;
    on_T2_hit?: string;
    on_T3_hit?: string;
  } | null;
  reasoning: string | null;
  created_at: string;
  // Enriched from stock_master JOIN (present when stock_master is populated)
  company_name?: string | null;
  sector?: string | null;
}

export interface SignalListResponse {
  total: number;
  items: Signal[];
}

export interface SignalFilters {
  category?: SignalCategory;
  min_rank?: number;
  min_gate?: number;
  side?: SignalSide;
  timeframe?: string;
  limit?: number;
  offset?: number;
}
