import type { SignalCategory, SignalSide } from "./signal";

export interface ScanResult {
  id: string;
  mode: string;
  status: "pending" | "running" | "done" | "failed";
  triggered_at: string;
  completed_at: string | null;
  signals_found: number | null;
  passed_filter: number | null;
  universe_size: number | null;
  duration_sec: number | null;
  error_message: string | null;
}

/** Partial signal shape received over WebSocket before DB persists full record. */
export interface StreamingSignal {
  symbol: string;
  category: SignalCategory;
  side: SignalSide | null;
  signal_timeframe: string | null;
  entry: number | null;
  stop_loss: number | null;
  t1: number | null;
  t2: number | null;
  t3: number | null;
  rr_t1: number | null;
  rr_t2: number | null;
  gate_strength: number | null;
  confidence: number | null;
  rank_score: number | null;
  htf_confirmed: boolean | null;
}
