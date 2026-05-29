export type AlertType =
  | "price_above"
  | "price_below"
  | "gate_score_gte"
  | "gate_score_lte"
  | "volume_spike"
  | "category_upgrade"
  | "breakout_detected"
  | "sl_breach_warning"
  | "target_proximity";

export type AlertStatus = "active" | "triggered" | "dismissed" | "expired";

export interface Alert {
  id: string;
  symbol: string;
  alert_type: AlertType;
  status: AlertStatus;
  threshold_value: number | null;
  timeframe: string | null;
  message: string | null;
  notify_via: string[];
  triggered_at: string | null;
  triggered_price: number | null;
  expires_at: string | null;
  created_at: string;
}

export interface CreateAlertRequest {
  symbol: string;
  alert_type: AlertType;
  threshold_value?: number;
  timeframe?: string;
  message?: string;
  notify_via?: string[];
}
