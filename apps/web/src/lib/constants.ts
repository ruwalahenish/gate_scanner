import type { SignalCategory, DisplayStatus } from "@/types/signal";

export const CATEGORY_COLORS = {
  INVESTMENT: "#22c55e",
  SWING:      "#6366f1",
  POSITIONAL: "#38bdf8",
  WATCH:      "#f59e0b",
  IGNORE:     "#64748b",
} as const;

export const CATEGORY_ORDER = ["INVESTMENT", "SWING", "POSITIONAL", "WATCH", "IGNORE"] as const;

// Categories that represent actionable BUY signals.
export const BUY_CATEGORIES: ReadonlySet<string> = new Set(["INVESTMENT", "SWING", "POSITIONAL"]);

// Maps raw signal category → user-facing label + display bucket.
export const CATEGORY_DISPLAY: Record<SignalCategory, { label: string; display: DisplayStatus }> = {
  INVESTMENT: { label: "Long-Term Buy",  display: "BUY"       },
  SWING:      { label: "Swing Buy",      display: "BUY"       },
  POSITIONAL: { label: "Positional Buy", display: "BUY"       },
  WATCH:      { label: "Watch",          display: "WATCH"     },
  IGNORE:     { label: "No Action",      display: "NO_ACTION" },
};

// Unified color token — canonical source for all signal/status colors.
// Components should import from here instead of using raw hex strings.
export const STATUS_COLORS = {
  INVESTMENT:     "#22c55e",
  SWING:          "#6366f1",
  POSITIONAL:     "#38bdf8",
  WATCH:          "#f59e0b",
  IGNORE:         "#64748b",
  "Long-Term Buy": "#22c55e",
  "Swing Buy":     "#6366f1",
  "Positional Buy":"#38bdf8",
  "Watch":         "#f59e0b",
  "No Action":     "#64748b",
} as const;

// GATE score colors and thresholds — single source for GATEBar, ScoreBar, etc.
export const GATE_COLOR = {
  HIGH: "#22c55e",
  MID:  "#6366f1",
  LOW:  "#f59e0b",
  FAIL: "#ef4444",
} as const;

export const GATE_THRESHOLDS = {
  HIGH: 70,
  MID:  55,
  LOW:  40,
} as const;

// Surface/overlay tokens — replaces scattered rgba strings throughout components.
export const SURFACE = {
  hover:        "rgba(255,255,255,0.025)",
  hoverStrong:  "rgba(255,255,255,0.06)",
  border:       "rgba(255,255,255,0.06)",
  borderStrong: "rgba(255,255,255,0.1)",
  overlay:      "rgba(0,0,0,0.15)",
  primary10:    "rgba(99,102,241,0.1)",
  primary15:    "rgba(99,102,241,0.15)",
} as const;

// Standardized spacing scale — use these in sx props for consistent padding/gaps.
export const SPACING = {
  cardPx:     2,
  rowPy:      0.75,
  sectionGap: 2,
} as const;

// Animation duration tokens (ms).
export const ANIM = {
  fast:   120,
  normal: 200,
  slow:   300,
} as const;

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
