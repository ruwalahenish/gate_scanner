"""
core/config.py
===============
Central configuration for the GATE Scanner engine.
All tunable constants live here — no magic numbers in engines.

NOTE: Runtime environment settings (database_url, redis_url, etc.) are in
      app/config.py. This file contains only pure Python constants.
"""

# -----------------------------------------------------------------------------
# EMA STRUCTURE
# -----------------------------------------------------------------------------
EMA_PERIODS = [20, 50, 100, 200]

# Map "correction depth" to which EMA price is testing
EMA_CORRECTION_MAP = {
    1: 20,    # first correction tests EMA20
    2: 50,    # second correction tests EMA50
    3: 100,   # third correction tests EMA100
    4: 200,   # major correction tests EMA200
}

# Proximity (% of price) within which we consider price "at" an EMA
EMA_TOUCH_TOLERANCE = 0.015  # 1.5%

# Monthly exception: for NIFTY_50 blue-chip/index stocks, corrections on the
MONTHLY_BLUECHIP_MAX_EMA = 100

# Minimum size of the impulsive leg INTO the swing high being corrected, expressed
# as a multiple of ATR(14) at that swing high. Without this, a choppy stock whose
# tiny swings happen to graze EMA200 could pass Check B with no genuine prior
# trend to correct from (§1: "Trend -> Correction -> Trend").
MIN_PRIOR_TREND_ATR_MULT = 3.0

# -----------------------------------------------------------------------------
# TIMEFRAME HIERARCHY
# -----------------------------------------------------------------------------
# yfinance interval strings
TIMEFRAMES = {
    "very_high_vol": ["1m", "3m", "5m", "15m"],  # 1m/3m added; 10m not in yfinance
    "high_vol":      ["30m", "60m"],
    "medium_vol":    ["4h", "1d"],                # 4h synthesized from 60m
    "low_vol":       ["1wk", "1mo"],
}

# Ordered from smallest to largest — used for hierarchy / SL mapping
TIMEFRAME_ORDER = ["1m", "3m", "5m", "15m", "30m", "60m", "4h", "1d", "1wk", "1mo"]

# History lookback per timeframe (yfinance period strings)
# NOTE: yfinance only provides 1m data for 7 days, 3m/5m for 60 days
TIMEFRAME_HISTORY = {
    "1m":  "7d",
    "3m":  "7d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "4h":  "730d",   # synthesized from 60m in data_fetcher
    "1d":  "5y",
    "1wk": "10y",
    "1mo": "max",
}

# Larger -> Smaller : the smaller-TF EMA200 is the SL for the larger-TF breakout
# Rule: "Smaller timeframe EMA200 acts as SL for larger timeframe breakout."
SL_TIMEFRAME_MAP = {
    "1mo": "1wk",
    "1wk": "1d",
    "1d":  "4h",    # daily breakout -> 4h EMA200 as SL (was "60m")
    "4h":  "60m",
    "60m": "15m",
    "30m": "15m",
    "15m": "5m",
    "5m":  "3m",    # was "5m" (self-reference bug) — now maps to "3m"
    "3m":  "1m",
    "1m":  "1m",    # no lower TF — signal_engine uses ATR fallback
}

# -----------------------------------------------------------------------------
# TARGET EXPECTANCY (move size as fraction of entry price)
# -----------------------------------------------------------------------------
# (T1_low, T3_high)  — T2 interpolated, T1/T2/T3 scaled across the range
TARGET_EXPECTANCY = {
    "1mo": (8.00, 12.00),    # 8x – 12x (massive multi-year trends)
    "1wk": (2.00, 3.00),     # 2x – 3x
    "1d":  (0.50, 0.70),     # 50–70%
    "4h":  (0.35, 0.40),     # 35–40%
    "60m": (0.20, 0.25),     # 20–25%
    "30m": (0.10, 0.15),
    "15m": (0.07, 0.10),
    "5m":  (0.05, 0.07),     # 5–7%
    "3m":  (0.03, 0.04),     # 3–4%
    "1m":  (0.03, 0.04),     # 3–4%
}

# -----------------------------------------------------------------------------
# CORRECTION DURATION (bars elapsed for a typical correction, per TF)
# Used by structure_engine to compute correction_age_pct
# -----------------------------------------------------------------------------
CORRECTION_DURATIONS = {
    "1mo": (120, 132),   # 10–11 years × 12 months/yr
    "1wk": (104, 130),   # 2–2.5 years × 52 weeks/yr
    "1d":  (125, 250),   # 6–12 months × ~21 trading days/month
    "4h":  (60,  120),   # ~2–4 months @ ~1.5 4h-bars/trading-day
    "60m": (80,  160),   # ~2–4 months @ ~6 1h-bars/trading-day
    "30m": (80,  160),
    "15m": (60,  120),
    "5m":  (100, 200),
    "3m":  (100, 200),
    "1m":  (100, 200),
}

# -----------------------------------------------------------------------------
# GATE DETECTION THRESHOLDS
# -----------------------------------------------------------------------------
# Bollinger Band width percentile (vs trailing window) under which we call it "squeeze"
BB_SQUEEZE_PERCENTILE = 20   # bottom 20% of last N bars
BB_LOOKBACK = 100

# ATR percentile threshold (lower = tighter contraction)
ATR_SQUEEZE_PERCENTILE = 25
ATR_LOOKBACK = 100

# EMA compression: max-min of EMAs divided by price < this -> compressed
EMA_COMPRESSION_THRESHOLD = 0.04   # 4%

# Narrow range candle: last N candles, average range / ATR
NR_LOOKBACK = 5

# Volume contraction: recent vol mean / longer vol mean
VOL_CONTRACTION_LOOKBACK_SHORT = 10
VOL_CONTRACTION_LOOKBACK_LONG = 50

# ADX threshold for contraction: ADX <= this is considered weak trend / sideways
ADX_CONTRACTION_WEAK = 15   # ADX <= 15 → score = 1.0 (maximum contraction signal)
ADX_CONTRACTION_STRONG = 35  # ADX >= 35 → score = 0.0 (no contraction signal)

# -----------------------------------------------------------------------------
# CONTRACTION SUB-SCORE WEIGHTS (must sum to 1.0)
# Feeds the "consolidation_strength" component of the per-TF GATE score.
# -----------------------------------------------------------------------------
CONTRACTION_WEIGHTS = {
    "bb_squeeze":      0.22,
    "atr_contraction": 0.18,
    "ema_compression": 0.22,
    "narrow_range":    0.13,
    "volume_contract": 0.13,
    "adx_contraction": 0.12,   # low ADX confirms the contraction phase
}

# -----------------------------------------------------------------------------
# PER-TIMEFRAME GATE SCORE WEIGHTS (technical gate; must sum to 1.0)
# The per-TF gate blends consolidation tightness, breakout proximity, and
# volume pattern (§3: Volume is a required tool for breakout confirmation).
# -----------------------------------------------------------------------------
GATE_TF_WEIGHTS = {
    "consolidation_strength": 0.50,   # the CONTRACTION_WEIGHTS composite
    "breakout_proximity":     0.25,   # closeness to range_high (peaks in BUY_ZONE)
    "volume_pattern":         0.25,   # dry-up during base + buildup near top
}

# -----------------------------------------------------------------------------
# SIGNAL-LEVEL GATE COMPOSITE WEIGHTS (final gate_strength; must sum to 1.0)
# Combines the signal-TF technical gate with MTF trend alignment.
# -----------------------------------------------------------------------------
GATE_WEIGHTS = {
    "technical_gate":  0.60,   # per-TF gate on the signal timeframe
    "trend_alignment": 0.40,   # MTF agreement (bigger picture bullish)
}

# -----------------------------------------------------------------------------
# COMPOSITE SCORE WEIGHTS for ranking (must sum to 1.0)
# Pure GATE strategy ranking: gate quality + breakout readiness + risk-reward.
# -----------------------------------------------------------------------------
RANK_WEIGHTS = {
    "gate_strength":      0.55,   # the GATE_WEIGHTS composite
    "breakout_readiness": 0.25,   # how primed the breakout is (state + proximity)
    "rr_ratio":           0.20,   # structural risk-reward
}

# -----------------------------------------------------------------------------
# CONSOLIDATION-RANGE / BREAKOUT-STATE MODEL
# The "gate" is the consolidation box. A BUY signal is generated ONLY when price
# has already broken out (BREAKOUT_CONFIRMED). BUY_ZONE = price approaching the
# gate top but not yet through it → WATCH only, never actionable (§6/§7).
# -----------------------------------------------------------------------------
RANGE_LOOKBACK         = 60      # bars on the signal TF used to detect the box (primary)
RANGE_LOOKBACK_FALLBACKS = [40, 30]  # shorter windows tried when primary box is too tall;
                                     # lets the detector find a base at EMA200 even when the
                                     # prior correction leg is still inside the 60-bar window
RANGE_MIN_DURATION     = 12      # box must persist >= this many bars to be valid
RANGE_MAX_HEIGHT_PCT   = 0.25    # box height (high-low)/low must be <= 25% (a base, not a trend leg)
RANGE_TIGHTNESS_ATR_MULT = 2.5   # recent ATR <= box_height/this → tight coil

# Breakout proximity bands (distance of close vs range_high, as a fraction)
BUY_ZONE_MAX_PCT          = 0.04   # close within 4% BELOW range_high → BUY_ZONE (WATCH)
BREAKOUT_CONFIRM_MAX_PCT  = 0.03   # close 0–3% ABOVE range_high → fresh BREAKOUT_CONFIRMED
EXTENDED_PCT              = 0.03   # close > 3% above range_high → EXTENDED (already moved → reject)
BREAKOUT_TRIGGER_BUFFER_PCT = 0.005  # entry level = range_high * (1 + this), i.e. just above gate top

# Only BREAKOUT_CONFIRMED triggers a BUY signal. BUY_ZONE → WATCH via classifier.
ACTIONABLE_BREAKOUT_STATES = ("BREAKOUT_CONFIRMED",)

# Setup expiry: max consecutive bars price may "wait at the gate" (between EMA200
# and range_high) before the setup is considered dead. §12 specifies 5–7 bars.
SETUP_EXPIRY_BARS = 7

# Level-freshness filter: a breakout is only "fresh" (§6C: a real, convincing
# breakout, not a "weak poke") if the box's range_high hasn't already failed
# repeatedly nearby. Bars further back than the current box are scanned for
# prior approaches to the same level that never closed decisively above it.
LEVEL_FRESHNESS_LOOKBACK      = 150   # bars before the current box to scan
LEVEL_FRESHNESS_TOLERANCE     = 0.02  # High within 2% of the level counts as a "test"
LEVEL_FRESHNESS_MAX_FAILURES  = 1     # more than this many failed tests → reject as chased

# Minimum blended per-TF GATE score (consolidation tightness + breakout proximity +
# volume pattern) for the gate to be considered genuinely "shut." Drives both the
# BUY-path is_gate flag and WATCH eligibility, so a watched setup is held to the
# exact same structural bar as an actionable one — just not broken out yet.
GATE_SCORE_THRESHOLD = 55.0

# Volume pickup (recent 3-bar avg / base avg) required to call a breakout's volume
# "strong confirmation," not just a mild uptick.
VOLUME_BUILDUP_MIN_RATIO = 1.4

# Breakout candle range must be at least this multiple of ATR(14) to count as
# "bigger-than-usual" (§6C) — excludes weak/doji/false-breakout candles.
BREAKOUT_CANDLE_ATR_MULT = 1.3

# Hard floor on the composite confidence score (see signal_engine._confidence) —
# a signal below this is rejected outright rather than merely ranked lower.
MIN_CONFIDENCE_SCORE = 65.0

# -----------------------------------------------------------------------------
# FIBONACCI EXTENSION TARGETS (anchored to consolidation base, §10)
# T = range_low + multiplier × (range_high − range_low)
# -----------------------------------------------------------------------------
FIB_EXT_T1 = 1.272   # first partial — 1.272 extension
FIB_EXT_T2 = 1.618   # main target   — golden ratio extension
FIB_EXT_T3 = 2.618   # extended run

# -----------------------------------------------------------------------------
# CLASSIFICATION RULES
# Five lists per GATE strategy §14: Investment, Swing, Positional, Watch, Ignore.
# A BUY-category signal (INVESTMENT/SWING/POSITIONAL) is emitted only when an
# actionable breakout setup exists; otherwise WATCH (forming) or IGNORE.
# NOTE: POSITIONAL (1h–2h setups) requires "60m" in SCAN_TIMEFRAMES to activate.
# -----------------------------------------------------------------------------
CATEGORY_RULES = {
    "INVESTMENT":  {"weekly_bull": True,  "monthly_bull": True,  "min_score": 75},
    "SWING":       {"daily_bull": True,   "min_gate": 65,        "min_score": 70},
    "POSITIONAL":  {"hourly_bull": True,  "min_gate": 45,        "min_score": 50},
    # WATCH's quality bar is GATE_SCORE_THRESHOLD (same "gate shut" cutoff as an
    # actionable gate) enforced directly in classifier.py, not a separate number here.
    "WATCH":       {"no_breakout_yet": True},
    "IGNORE":      {},   # default bucket
}

# -----------------------------------------------------------------------------
# RISK / SIGNAL FILTERS
# -----------------------------------------------------------------------------
MIN_RR_RATIO = 2.0           # required risk-reward ("sufficient upside potential remaining");
                              # strategy §16 states 1.5 as an absolute floor — this scanner-level
                              # bar is deliberately higher to surface only high-conviction setups
MIN_AVG_VOLUME = 100_000     # liquidity floor (20-bar avg daily volume)
MIN_PRICE = 20.0             # avoid penny stocks
MAX_SL_DISTANCE_PCT = 0.08   # SL no further than ~8% from entry for daily swing trades

# GATE position requirement: the GATE squeeze forms AT the 200 EMA (§1–§3).
# Price must be within this fraction below EMA200 for a valid GATE signal or WATCH.
# Stocks more than GATE_PRICE_MIN_EMA200 below EMA200 are in a bear breakdown, not
# a correction-to-EMA200 setup.
GATE_PRICE_MIN_EMA200 = 0.05   # allow up to 5% below EMA200 (EMA cluster spans EMA200)
# Upper bound: the consolidation box floor must not be more than this fraction ABOVE EMA200.
# If range_low > EMA200 × (1 + this), the stock has already broken out and extended well above
# EMA200 — the tight coil we detect is a post-breakout base, not a correction-to-EMA200 GATE.
GATE_RANGE_MAX_ABOVE_EMA200 = 0.10   # range_low must be ≤ EMA200 × 1.10

# Confidence adjustments applied as multipliers in _confidence()
INVALID_SEQUENCE_PENALTY = 0.08   # -8% when EMA bounce sequence is out of order
FIB_CONFLUENCE_BOOST     = 0.08   # +8% when entry is in the Fibonacci 0.382–0.618 zone

# -----------------------------------------------------------------------------
# STOCK UNIVERSE
# -----------------------------------------------------------------------------
# Nifty 50 + a few high-liquidity F&O names. Replace/extend as needed.
# Use NSE Yahoo suffix ".NS"
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC",
    "LT", "SBIN", "KOTAKBANK", "AXISBANK", "HINDUNILVR", "BAJFINANCE",
    "MARUTI", "ASIANPAINT", "HCLTECH", "SUNPHARMA", "TITAN", "ULTRACEMCO",
    "WIPRO", "NTPC", "ONGC", "M&M", "POWERGRID", "NESTLEIND", "TATAMOTORS",
    "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV",
    "GRASIM", "HINDALCO", "DRREDDY", "CIPLA", "TECHM", "INDUSINDBK",
    "EICHERMOT", "BRITANNIA", "BPCL", "DIVISLAB", "HEROMOTOCO", "APOLLOHOSP",
    "TATACONSUM", "UPL", "BAJAJ-AUTO", "SBILIFE", "HDFCLIFE", "LTIM",
]

NIFTY_NEXT_50_SAMPLE = [
    "DMART", "PIDILITIND", "GODREJCP", "DABUR", "MARICO", "AMBUJACEM",
    "VEDL", "GAIL", "SIEMENS", "HAVELLS", "ICICIPRULI", "MUTHOOTFIN",
    "BANKBARODA", "PNB", "CANBK", "ZOMATO", "PAYTM", "NYKAA",
]

DEFAULT_UNIVERSE = NIFTY_50 + NIFTY_NEXT_50_SAMPLE


def yf_symbol(sym: str) -> str:
    """Append NSE Yahoo suffix if not already suffixed (.NS or .BO).

    Index symbols (Yahoo uses a '^' prefix, e.g. ^NSEI, ^NSEBANK) are passed
    through unchanged so relative-strength / sector-momentum fetches resolve.
    """
    if sym.startswith("^") or sym.endswith((".NS", ".BO")):
        return sym
    return f"{sym}.NS"


# -----------------------------------------------------------------------------
# DAILY TIMEFRAME STRATEGY — the platform currently scans 1d bars.
# POSITIONAL (§14, 1h-2h setups) is naturally inactive because "60m" is not in
# SCAN_TIMEFRAMES below — classifier.py's hourly checks see no data and skip it.
# Add "60m" to SCAN_TIMEFRAMES to re-enable POSITIONAL classification.
# -----------------------------------------------------------------------------
# The entry signal is ALWAYS generated on the daily (1d) timeframe.
# 4h bars are fetched to compute the SL (SL_TIMEFRAME_MAP["1d"] = "4h").
# 1wk bars are fetched for HTF confirmation (direction agreement).
SCAN_TIMEFRAME  = "1d"                  # signal generation TF — never changes
SCAN_TIMEFRAMES = ["4h", "1d", "1wk"]  # fetch set: SL source | entry | HTF confirm
