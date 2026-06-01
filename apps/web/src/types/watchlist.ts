export type WatchlistStatus =
  | "active"
  | "buy_triggered"
  | "target_hit"
  | "sl_hit"
  | "closed";

export type WatchlistSource = "manual" | "scanner";

export interface WatchlistItem {
  id: string;
  symbol: string;
  added_at: string;
  notes: string | null;
  tags: string[] | null;
  signal_id: string | null;
  status: WatchlistStatus;
  gate_strength: number | null;
  rank_score: number | null;
  entry: number | null;
  stop_loss: number | null;
  t1: number | null;
  last_checked_at: string | null;
  source: WatchlistSource;
}

export interface WatchlistHistoryEvent {
  id: string;
  symbol: string;
  event: "added" | "status_change" | "gate_update" | "removed";
  from_status: WatchlistStatus | null;
  to_status: WatchlistStatus | null;
  details: Record<string, unknown>;
  occurred_at: string;
}
