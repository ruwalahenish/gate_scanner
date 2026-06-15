/**
 * tradeSetup.ts
 * =============
 * Single source of truth for the "trade setup" view-model rendered by
 * TradeSetupPanel across the scanner table, stock detail page, and watchlist.
 *
 * Resolves the two payload shapes the backend emits:
 *   - Stored/streaming SIGNAL: lowercase keys (t1/t2/t3, rr_t1/rr_t2/rr_t3, stop_loss)
 *   - Live ANALYSIS signal:    capital-T keys (T1/T2/T3, rr.{T1,T2,T3}, stop_loss)
 *
 * `provenance` encodes the WATCH semantics:
 *   - "confirmed"   → a real, triggered setup from a completed scan
 *   - "anticipated" → provisional levels computed on-demand for a WATCH stock
 *                     (label "Anticipated — not yet triggered")
 *   - "none"        → live analysis found no qualifying setup yet (watching for breakout)
 */
import type { Signal, SignalCategory, SignalSide } from "@/types/signal";
import type { Stock } from "@/types/stock";
import type { WatchlistItem } from "@/types/watchlist";

export type SetupProvenance = "confirmed" | "anticipated" | "none";

export interface TradeSetup {
  symbol: string;
  side: SignalSide | null;
  entry: number | null;
  stopLoss: number | null;
  targets: { t1: number | null; t2: number | null; t3: number | null };
  rr: { t1: number | null; t2: number | null; t3: number | null };
  /** Critical breakout trigger and consolidation box bounds. */
  breakoutLevel: number | null;
  rangeHigh: number | null;
  rangeLow: number | null;
  breakoutState: string | null;
  slDistancePct: number | null;
  atr: number | null;
  gateStrength: number | null;
  confidence: number | null;
  rankScore: number | null;
  structureQuality: number | null;
  mtfAlignmentPct: number | null;
  breakoutProbability: number | null;
  volatilityCompression: number | null;
  flags: {
    htfConfirmed: boolean | null;
    correctionValidated: boolean | null;
    bounceSequenceValid: boolean | null;
    fibConfluence: boolean | null;
  };
  signalTimeframe: string | null;
  slTimeframe: string | null;
  trendDirection: string | null;
  phase: string | null;
  reasoning: string | null;
  category: SignalCategory | null;
  displayCategory: string | null;
  provenance: SetupProvenance;
  hasLevels: boolean;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function bool(v: unknown): boolean | null {
  return typeof v === "boolean" ? v : null;
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

const EMPTY_FLAGS = {
  htfConfirmed: null,
  correctionValidated: null,
  bounceSequenceValid: null,
  fibConfluence: null,
} as const;

/** Build a setup from a stored/streaming scanner Signal (lowercase keys). */
export function fromSignal(
  s: Signal,
  provenanceOverride?: SetupProvenance,
): TradeSetup {
  const entry = num(s.entry);
  const provenance: SetupProvenance =
    provenanceOverride ?? (entry != null ? "confirmed" : "anticipated");
  return {
    symbol: s.symbol,
    side: s.side,
    entry,
    stopLoss: num(s.stop_loss),
    targets: { t1: num(s.t1), t2: num(s.t2), t3: num(s.t3) },
    rr: { t1: num(s.rr_t1), t2: num(s.rr_t2), t3: num(s.rr_t3) },
    breakoutLevel: num(s.breakout_level),
    rangeHigh: num(s.range_high),
    rangeLow: num(s.range_low),
    breakoutState: s.breakout_state ?? null,
    slDistancePct: num(s.sl_distance_pct),
    atr: num(s.atr),
    gateStrength: num(s.gate_strength),
    confidence: num(s.confidence),
    rankScore: num(s.rank_score),
    structureQuality: num(s.structure_quality),
    mtfAlignmentPct: num(s.mtf_alignment_pct),
    breakoutProbability: num(s.breakout_probability),
    volatilityCompression: num(s.volatility_compression),
    flags: {
      htfConfirmed: bool(s.htf_confirmed),
      correctionValidated: bool(s.correction_validated),
      bounceSequenceValid: bool(s.bounce_sequence_valid),
      fibConfluence: bool(s.fib_confluence),
    },
    signalTimeframe: s.signal_timeframe,
    slTimeframe: s.sl_timeframe,
    trendDirection: s.trend_direction,
    phase: s.phase,
    reasoning: s.reasoning,
    category: s.category ?? null,
    displayCategory: s.display_category ?? null,
    provenance,
    hasLevels: entry != null,
  };
}

/**
 * Build a setup from the live analysis endpoint response
 * (`GET /api/stocks/{symbol}/analysis` → { signal, summary, per_tf }).
 * `signal` uses capital-T keys and may be null (no qualifying setup).
 */
export function fromLiveAnalysis(
  symbol: string,
  analysisData: unknown,
  opts?: { category?: SignalCategory | null; provenance?: SetupProvenance },
): TradeSetup {
  const data = (analysisData ?? {}) as Record<string, any>;
  const sig = data.signal as Record<string, any> | null | undefined;
  const summary = (data.summary ?? {}) as Record<string, any>;

  // Scores fall back to the MTF summary when no full signal was built (WATCH).
  const summaryGate = num(summary.gate_score) ?? num(summary.best_gate);
  const summaryAlign = num(summary?.alignment?.alignment_pct);
  const summaryStruct = num(summary.structure_quality);

  if (!sig) {
    return {
      symbol,
      side: null,
      entry: null,
      stopLoss: null,
      targets: { t1: null, t2: null, t3: null },
      rr: { t1: null, t2: null, t3: null },
      breakoutLevel: null,
      rangeHigh: null,
      rangeLow: null,
      breakoutState: null,
      slDistancePct: null,
      atr: null,
      gateStrength: summaryGate,
      confidence: null,
      rankScore: null,
      structureQuality: summaryStruct,
      mtfAlignmentPct: summaryAlign,
      breakoutProbability: null,
      volatilityCompression: null,
      flags: { ...EMPTY_FLAGS },
      signalTimeframe: str(summary.leading_tf),
      slTimeframe: null,
      trendDirection: null,
      phase: null,
      reasoning: str(data.reasoning) ?? str(summary.reasoning),
      category: opts?.category ?? null,
      displayCategory: null,
      provenance: "none",
      hasLevels: false,
    };
  }

  const entry = num(sig.entry);
  return {
    symbol,
    side: (sig.side as SignalSide) ?? null,
    entry,
    stopLoss: num(sig.stop_loss),
    targets: { t1: num(sig.T1), t2: num(sig.T2), t3: num(sig.T3) },
    rr: { t1: num(sig.rr?.T1), t2: num(sig.rr?.T2), t3: num(sig.rr?.T3) },
    breakoutLevel: num(sig.breakout_level),
    rangeHigh: num(sig.range_high),
    rangeLow: num(sig.range_low),
    breakoutState: str(sig.breakout_state),
    slDistancePct: num(sig.sl_distance_pct),
    atr: num(sig.atr),
    gateStrength: num(sig.gate_strength) ?? summaryGate,
    confidence: num(sig.confidence),
    rankScore: num(sig.rank_score),
    structureQuality: num(sig.structure_quality) ?? summaryStruct,
    mtfAlignmentPct: num(sig.mtf_alignment_pct) ?? summaryAlign,
    breakoutProbability: num(sig.breakout_probability),
    volatilityCompression: num(sig.volatility_compression),
    flags: {
      htfConfirmed: bool(sig.htf_confirmed),
      correctionValidated: bool(sig.correction_validated),
      bounceSequenceValid: bool(sig.bounce_sequence_valid),
      fibConfluence: bool(sig.fib_confluence),
    },
    signalTimeframe: str(sig.signal_timeframe),
    slTimeframe: str(sig.sl_timeframe),
    trendDirection: str(sig.trend_direction),
    phase: str(sig.phase),
    reasoning: str(sig.reasoning),
    category: opts?.category ?? (str(sig.category) as SignalCategory | null),
    displayCategory: null,
    // Live analysis on a WATCH stock = provisional/anticipated; callers may override.
    provenance: opts?.provenance ?? (entry != null ? "anticipated" : "none"),
    hasLevels: entry != null,
  };
}

/** Build a partial setup from a watchlist row (only entry/SL/T1/gate/rank stored). */
export function fromWatchlistItem(item: WatchlistItem): TradeSetup {
  const entry = num(item.entry);
  return {
    symbol: item.symbol,
    side: null,
    entry,
    stopLoss: num(item.stop_loss),
    targets: { t1: num(item.t1), t2: null, t3: null },
    rr: { t1: null, t2: null, t3: null },
    breakoutLevel: null,
    rangeHigh: null,
    rangeLow: null,
    breakoutState: null,
    slDistancePct: null,
    atr: null,
    gateStrength: num(item.gate_strength),
    confidence: null,
    rankScore: num(item.rank_score),
    structureQuality: null,
    mtfAlignmentPct: null,
    breakoutProbability: null,
    volatilityCompression: null,
    flags: { ...EMPTY_FLAGS },
    signalTimeframe: null,
    slTimeframe: null,
    trendDirection: null,
    phase: null,
    reasoning: null,
    category: "WATCH",
    displayCategory: "Watch",
    provenance: "anticipated",
    hasLevels: entry != null,
  };
}

/** Build a setup from the latest stored scan signal embedded on a Stock row. */
export function fromStockLatest(stock: Stock): TradeSetup {
  const entry = num(stock.latest_entry);
  return {
    symbol: stock.symbol,
    side: (stock.latest_side as SignalSide) ?? null,
    entry,
    stopLoss: num(stock.latest_stop_loss),
    targets: { t1: num(stock.latest_t1), t2: null, t3: null },
    rr: { t1: num(stock.latest_rr_t1), t2: null, t3: null },
    breakoutLevel: null,
    rangeHigh: null,
    rangeLow: null,
    breakoutState: null,
    slDistancePct: null,
    atr: null,
    gateStrength: num(stock.latest_gate_strength),
    confidence: num(stock.latest_confidence),
    rankScore: num(stock.latest_rank_score),
    structureQuality: null,
    mtfAlignmentPct: null,
    breakoutProbability: null,
    volatilityCompression: null,
    flags: { ...EMPTY_FLAGS },
    signalTimeframe: stock.latest_signal_timeframe,
    slTimeframe: null,
    trendDirection: null,
    phase: null,
    reasoning: null,
    category: (stock.latest_category as SignalCategory) ?? null,
    displayCategory: null,
    provenance: entry != null ? "confirmed" : "none",
    hasLevels: entry != null,
  };
}

/** Lowercase level shape consumed by GATEChart. */
export function toChartLevels(ts: TradeSetup | null | undefined): {
  entry?: number | null;
  stop_loss?: number | null;
  t1?: number | null;
  t2?: number | null;
  t3?: number | null;
  breakout_level?: number | null;
} | null {
  if (!ts) return null;
  return {
    entry: ts.entry,
    stop_loss: ts.stopLoss,
    t1: ts.targets.t1,
    t2: ts.targets.t2,
    t3: ts.targets.t3,
    breakout_level: ts.breakoutLevel,
  };
}
