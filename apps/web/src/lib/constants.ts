export const CATEGORY_COLORS = {
  INVESTMENT: "#22c55e",
  SWING:      "#6366f1",
  POSITIONAL: "#38bdf8",
  WATCH:      "#f59e0b",
  IGNORE:     "#64748b",
} as const;

export const CATEGORY_ORDER = ["INVESTMENT", "SWING", "POSITIONAL", "WATCH", "IGNORE"] as const;

export const TIMEFRAME_LABELS: Record<string, string> = {
  "1m":  "1 Min",
  "5m":  "5 Min",
  "15m": "15 Min",
  "30m": "30 Min",
  "60m": "1 Hour",
  "4h":  "4 Hour",
  "1d":  "Daily",
  "1wk": "Weekly",
  "1mo": "Monthly",
};

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
