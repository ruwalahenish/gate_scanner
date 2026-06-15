export type SignalCategory = "INVESTMENT" | "SWING" | "POSITIONAL" | "BREAKOUT" | "WATCH" | "IGNORE";
export type SignalSide = "BUY" | "SELL";
export type DisplayStatus = "BUY" | "BREAKOUT" | "WATCH" | "NO_ACTION";
export type BreakoutState =
  | "BUY_ZONE"
  | "BREAKOUT_CONFIRMED"
  | "ACCUMULATION"
  | "EXTENDED"
  | "BROKEN_DOWN"
  | "NO_GATE";

export interface Signal {
  id: string;
  scan_id: string;
  symbol: string;
  category: SignalCategory;
  // User-facing labels added by the API layer
  display_status: DisplayStatus | null;
  display_category: string | null;  // "Long-Term Buy", "Swing Buy", "Positional Buy", "Watch", "No Action"
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
  // Strategy-rework fields (consolidation-range / breakout-state model)
  breakout_state: BreakoutState | null;
  range_high: number | null;
  range_low: number | null;
  breakout_level: number | null;
  measured_move: number | null;
  rs_score: number | null;
  sector_momentum: number | null;
  accumulation_score: number | null;
  fundamental_score: number | null;
  volume_buildup: boolean | null;
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
  // timeframe is always "1d" in this platform — not a user-facing filter
  limit?: number;
  offset?: number;
}
