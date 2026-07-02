export type SyncStatus = "pending" | "enriched" | "failed" | "delisted";
export type Exchange = "NSE" | "BSE";

export interface StockSearchResult {
  symbol: string;
  exchange: Exchange;
  company_name: string;
  isin: string | null;
  sector: string | null;
  in_nifty50: boolean;
  in_nifty500: boolean;
  market_cap: number | null;
}

export interface Stock extends StockSearchResult {
  series: string | null;
  face_value: number | null;
  listing_date: string | null;
  market_lot: number | null;
  in_nifty_next50: boolean;
  in_nifty100: boolean;
  in_midcap150: boolean;
  in_smallcap100: boolean;
  is_fno: boolean;
  industry: string | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  dividend_yield: number | null;
  eps: number | null;
  book_value: number | null;
  sync_status: SyncStatus;
  last_synced_at: string | null;
  sync_error: string | null;
  updated_at: string | null;
  created_at: string | null;
  // Latest scan signal data (null if stock has never appeared in a scan)
  latest_category: string | null;
  latest_rank_score: number | null;
  latest_gate_strength: number | null;
  latest_confidence: number | null;
  latest_side: string | null;
  latest_signal_timeframe: string | null;
  latest_entry: number | null;
  latest_stop_loss: number | null;
  latest_t1: number | null;
  latest_rr_t1: number | null;
  // Live price (inline from list endpoint)
  live_price: number | null;
}

export interface StockListResponse {
  total: number;
  items: Stock[];
}

export interface StockFilters {
  exchange?: Exchange;
  index_filter?: "nifty50" | "nifty_next50" | "nifty100" | "nifty500" | "midcap150" | "smallcap100" | "fno";
  sector?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

export interface StockSyncStats {
  total: number;
  by_exchange: Record<string, number>;
  by_sync_status: Record<SyncStatus, number>;
  index_sizes: Record<string, number>;
  last_synced_at: string | null;
}

// OHLCV bar with EMA overlays (returned by /api/stocks/{symbol}/chart-data)
export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema20: number | null;
  ema50: number | null;
  ema100: number | null;
  ema200: number | null;
}

export interface SyncTaskStatus {
  is_running: boolean;
  state: "idle" | "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY" | "UNKNOWN";
  task_id?: string;
  phases?: string[];
  started_at?: string;
  current_phase?: string | null;
  progress?: {
    processed: number;
    succeeded: number;
    failed: number;
  } | null;
  error?: string | null;
}
