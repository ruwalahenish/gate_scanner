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
# monthly timeframe end at EMA100, not EMA200 (BUG-1 fix)
MONTHLY_BLUECHIP_MAX_EMA = 100

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
# BUG FIX (C-3): "5m" previously mapped to itself — now correctly maps to "3m"
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
    "4h":  (0.35, 0.40),     # 35–40%  (BUG-3 fix: was absent)
    "60m": (0.20, 0.25),     # 20–25%
    "30m": (0.10, 0.15),
    "15m": (0.07, 0.10),
    "5m":  (0.05, 0.07),     # 5–7%
    "3m":  (0.03, 0.04),     # 3–4%  (MISS-4 fix: was absent)
    "1m":  (0.03, 0.04),     # 3–4%  (MISS-4 fix: was absent)
}

# -----------------------------------------------------------------------------
# CORRECTION DURATION (bars elapsed for a typical correction, per TF)
# (MISS-3 fix: strategy defines correction durations per timeframe)
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
# (C-2 fix: used by the new adx_contraction GATE component)
ADX_CONTRACTION_WEAK = 15   # ADX <= 15 → score = 1.0 (maximum contraction signal)
ADX_CONTRACTION_STRONG = 35  # ADX >= 35 → score = 0.0 (no contraction signal)

# -----------------------------------------------------------------------------
# GATE SCORE WEIGHTS (must sum to 1.0)
# (C-2 fix: added adx_contraction; weights redistributed proportionally)
# -----------------------------------------------------------------------------
GATE_WEIGHTS = {
    "bb_squeeze":      0.22,
    "atr_contraction": 0.18,
    "ema_compression": 0.22,
    "narrow_range":    0.13,
    "volume_contract": 0.13,
    "adx_contraction": 0.12,   # new: low ADX confirms the contraction phase
}

# -----------------------------------------------------------------------------
# COMPOSITE SCORE WEIGHTS for ranking
# -----------------------------------------------------------------------------
RANK_WEIGHTS = {
    "gate_strength":       0.30,
    "mtf_alignment":       0.25,
    "structure_quality":   0.20,
    "breakout_probability":0.15,
    "rr_ratio":            0.10,
}

# -----------------------------------------------------------------------------
# CLASSIFICATION RULES
# -----------------------------------------------------------------------------
# Minimum scores per category
CATEGORY_RULES = {
    "INVESTMENT":  {"weekly_bull": True,  "monthly_bull": True,  "min_score": 70},
    "SWING":       {"daily_bull": True,   "min_gate": 60,        "min_score": 60},
    "POSITIONAL":  {"hourly_bull": True,  "min_gate": 50,        "min_score": 50},
    "WATCH":       {"min_gate": 55,       "no_breakout_yet": True},
    "IGNORE":      {},   # default bucket
}

# -----------------------------------------------------------------------------
# RISK / SIGNAL FILTERS
# (S-2/S-3 fix: strategy document now matches these code-enforced thresholds)
# -----------------------------------------------------------------------------
MIN_RR_RATIO = 1.5           # minimum acceptable risk-reward at T1
MIN_AVG_VOLUME = 100_000     # liquidity floor (20-bar avg daily volume)  (S-4)
MIN_PRICE = 20.0             # avoid penny stocks  (S-4)
MAX_SL_DISTANCE_PCT = 0.12   # SL no further than 12% from entry  (S-3)

# Confidence penalty (0–1 subtracted from confidence multiplier) applied when
# the correction sequence or 200 EMA touch validation fails
UNVALIDATED_CORRECTION_PENALTY = 0.10   # 10% confidence reduction
INVALID_SEQUENCE_PENALTY = 0.08         # 8% confidence reduction
FIB_CONFLUENCE_BOOST = 0.08             # 8% confidence boost for Fibonacci confluence

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
    """Append NSE Yahoo suffix if not already suffixed (.NS or .BO)."""
    if sym.endswith((".NS", ".BO")):
        return sym
    return f"{sym}.NS"


# -----------------------------------------------------------------------------
# BACKTESTER DEFAULTS
# -----------------------------------------------------------------------------
BACKTEST_START_DATE    = "2020-01-01"
BACKTEST_END_DATE      = None          # None = today
BACKTEST_CAPITAL       = 1_000_000     # ₹10 lakh starting capital
BACKTEST_POSITION_PCT  = 0.05          # 5% of equity per trade
BACKTEST_MAX_POSITIONS = 10            # max concurrent open positions
BACKTEST_TIMEFRAME     = "1d"          # GATE strategy works best on daily

# -----------------------------------------------------------------------------
# DAILY TIMEFRAME STRATEGY — the entire GATE platform operates on 1d bars.
# -----------------------------------------------------------------------------
# The entry signal is ALWAYS generated on the daily (1d) timeframe.
# 4h bars are fetched to compute the SL (SL_TIMEFRAME_MAP["1d"] = "4h").
# 1wk bars are fetched for HTF confirmation (direction agreement).
SCAN_TIMEFRAME  = "1d"                  # signal generation TF — never changes
SCAN_TIMEFRAMES = ["4h", "1d", "1wk"]  # fetch set: SL source | entry | HTF confirm

# -----------------------------------------------------------------------------
# AUTOMATED PAPER TRADING (automation_service.py)
# BUY-category signals above this rank trigger automatic paper trades.
# -----------------------------------------------------------------------------
AUTO_TRADE_MIN_RANK        = 50     # category filter (INVESTMENT/SWING/POSITIONAL) is the sole quality gate
AUTO_TRADE_POSITION_SIZE_PCT = 0.05  # 5% of current_capital per trade
AUTO_TRADE_MAX_POSITIONS   = 10    # max simultaneous open auto positions
