<div align="center">

# 📊 GATE Scanner

### Volatility Contraction Scanner for the Indian Stock Market

**Automatically detect high-probability breakout setups across 1,900+ NSE & BSE stocks**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](#prerequisites)
[![License](https://img.shields.io/badge/license-Private-red?style=for-the-badge)](#license)
[![Market](https://img.shields.io/badge/market-NSE%20%7C%20BSE-orange?style=for-the-badge)](#overview)

---

*Built on the GATE (Gap And Trend Expansion) trading strategy — a systematic framework that identifies stocks transitioning from volatility contraction to expansion using EMA-based correction & cycle analysis.*

</div>

---

## 📑 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
  - [Full Multi-Timeframe Scan](#1-full-multi-timeframe-scan)
  - [Daily EOD Scan](#2-daily-eod-scan-recommended)
  - [Backtesting](#3-backtesting)
  - [Automated Scheduling](#4-automated-scheduling)
- [Output Files](#output-files)
- [Project Structure](#project-structure)
- [Configuration Reference](#configuration-reference)
- [Column Reference](#column-reference)
- [Signal Categories](#signal-categories)
- [Signal Quality Flags](#signal-quality-flags)
- [FAQ & Troubleshooting](#faq--troubleshooting)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)

---

## Overview

**GATE Scanner** is a Python-based stock screening tool designed for the Indian equity market (NSE & BSE). It scans stocks across multiple timeframes, detects **volatility contraction patterns** (GATEs), and generates actionable trade signals with precise entry, stop loss, and target levels.

The scanner implements the **GATE Trading Strategy** — a systematic approach based on the observation that markets alternate between contraction (low volatility) and expansion (high volatility) phases. By identifying stocks in tight contraction (a "GATE formation"), the scanner finds setups with high breakout probability and favorable risk-reward ratios.

### What Problem Does It Solve?

Manually screening 700+ stocks across multiple timeframes for volatility contraction patterns is impossible. This scanner:

- **Automates the entire process** — from data fetching to signal generation to report building
- **Applies strict risk management** — every signal must pass minimum RR, SL distance, and liquidity filters
- **Ranks and classifies opportunities** — so you see the best setups first, categorized by trading style
- **Generates interactive HTML reports** — with embedded charts, sortable tables, and per-signal reasoning

---

## Key Features

| Feature | Description |
|---------|-------------|
| 🔍 **Multi-Timeframe Analysis** | Scans 10 timeframes (1m → 1mo) simultaneously |
| 📈 **6-Component GATE Score** | Weighted contraction score (BB squeeze, ATR, EMA compression, narrow range, volume, ADX) |
| 🎯 **Auto Signal Generation** | Entry, SL (EMA200 anchored), T1/T2/T3 targets with ATR + expectancy projection |
| ⚖️ **Risk Management Filters** | Min RR ≥ 1.5x, SL ≤ 12%, price ≥ ₹20, avg volume ≥ 1L |
| 📊 **5-Category Classification** | INVESTMENT · SWING · POSITIONAL · WATCH · IGNORE |
| 🌐 **Interactive HTML Reports** | Dark-themed, sortable tables with embedded Plotly candlestick charts |
| 📅 **Automated Scheduling** | Post-market cron scheduler (Mon–Fri, 4 PM IST) |
| 🧪 **Walk-Forward Backtester** | No look-ahead bias; equity curves, drawdown, per-trade charts |
| 💾 **Disk Cache** | Parquet-based caching with 1h TTL (24h for universe lists) |
| 🔧 **Fully Configurable** | All thresholds, weights, and rules in a single `config.py` |

---

## How It Works

The GATE strategy is built on a simple principle:

> **Do not look for the trend — look for the correction.**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        GATE Formation                              │
│                                                                    │
│  Price:  ──────╱╲──────────────────────────────────╱── breakout!   │
│              ╱    ╲     tight range (GATE)        ╱                │
│            ╱       ╲──╱──╲──╱──╲──╱──╲──╱──╲──╱──                 │
│          ╱                                                         │
│                                                                    │
│  EMAs:   All 4 EMAs (20/50/100/200) compress to < 4% of price    │
│  BB:     Bollinger Bands squeeze to bottom 20th percentile         │
│  ATR:    Average True Range drops to bottom 25th percentile        │
│  Volume: 10-bar avg volume < 50-bar avg volume                     │
│  ADX:    Trend strength drops ≤ 15 (sideways)                      │
│                                                                    │
│  When all 6 compress → GATE Score ≥ 55 → Signal generated         │
└─────────────────────────────────────────────────────────────────────┘
```

**The scanner then:**
1. Finds the **leading timeframe** (smallest TF with GATE ≥ 55)
2. Confirms direction on the **next-larger timeframe**
3. Calculates **entry / SL / targets** with structural anchoring
4. Validates against **risk management filters** (RR, SL distance, liquidity)
5. Ranks by a **composite score** and classifies into trading categories

---

## Architecture

The scanner runs a **5-stage sequential pipeline**:

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Stage 1    │    │   Stage 2    │    │   Stage 3    │    │   Stage 4    │    │   Stage 5    │
│              │    │              │    │              │    │              │    │              │
│   Scanner    │───►│  MTF Analysis│───►│    Risk      │───►│   Ranking    │───►│   Report     │
│   Agent      │    │    Agent     │    │    Agent     │    │    Agent     │    │    Agent     │
│              │    │              │    │              │    │              │    │              │
│ Fetch OHLCV  │    │ EMA Engine   │    │ Signal Build │    │ Score & Rank │    │ Console/CSV  │
│ Filter by    │    │ Contraction  │    │ Entry/SL/Tgt │    │ Classify     │    │ JSON/HTML    │
│ liquidity    │    │ Structure    │    │ RR/SL check  │    │ Sort         │    │ Charts       │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
     ▲                    ▲                                                          │
     │                    │                                                          ▼
  yfinance           3 engines per TF:                                      gate_output/
  (parallel)         • ema_engine.py                                        ├── signals.csv
                     • contraction_engine.py                                ├── signals.json
                     • structure_engine.py                                  ├── scan_report.html
                                                                           └── charts/*.html
```

### Engine Details

| Engine | File | Purpose |
|--------|------|---------|
| **EMA Engine** | `ema_engine.py` | EMA stack state, correction depth, bounce sequence validation |
| **Contraction Engine** | `contraction_engine.py` | 6-component GATE score (0–100), breakout probability |
| **Structure Engine** | `structure_engine.py` | Trend direction, correction type (price/time), phase detection |
| **Signal Engine** | `signal_engine.py` | Entry/SL/target calculation, confidence scoring, quality flags |
| **Ranking Engine** | `ranking_engine.py` | Composite rank score, category classification |

---

## Prerequisites

- **Python 3.10** or later
- **Internet connection** — for fetching live market data via yfinance
- **Operating System** — Windows, macOS, or Linux

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/gate-scanner.git
cd gate-scanner
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Core dependencies:**

| Package | Version | Purpose |
|---------|---------|---------|
| `pandas` | ≥ 2.0.0 | Data manipulation & analysis |
| `numpy` | ≥ 1.24.0 | Numerical computations |
| `yfinance` | ≥ 0.2.40 | Market data provider (NSE/BSE via Yahoo Finance) |
| `requests` | ≥ 2.31.0 | HTTP requests for universe list fetching |
| `rich` | ≥ 13.0.0 | Beautiful console output (tables, progress bars) |
| `plotly` | ≥ 5.18.0 | Interactive HTML charts |

**Optional dependencies:**

| Package | Purpose |
|---------|---------|
| `apscheduler` | Automated daily scheduling (`pip install apscheduler`) |

### 4. Verify Installation

```bash
python -m gate_scanner.main --help
```

You should see the full CLI help output with all available options.

---

## Quick Start

### Run Your First Scan (3 stocks, ~30 seconds)

```bash
python -m gate_scanner.main --universe RELIANCE TCS HDFCBANK
```

This will:
1. Fetch OHLCV data for 3 stocks across 5 timeframes
2. Run the GATE analysis pipeline
3. Print a categorized signal table to your terminal
4. Save outputs to `./gate_output/`

### Run the Daily Scanner (~700 stocks, ~5 minutes)

```bash
python -m gate_scanner.daily_scanner
```

### Open the HTML Report

After any scan, open the interactive report:

```bash
# The report is saved at:
# ./gate_output/daily/scan_report.html  (daily scanner)
# ./gate_output/scan_report.html        (full scanner)
```

The HTML report includes:
- A sortable, filterable signal table grouped by category
- Per-signal Plotly candlestick charts with EMA overlays
- Auto-generated reasoning for each signal

---

## Usage Guide

### 1. Full Multi-Timeframe Scan

Scans across multiple timeframes (15m, 60m, 1d, 1wk, 1mo by default):

```bash
# Default universe (Nifty 50 + Next 50 + Midcap 150)
python -m gate_scanner.main

# Custom stock list
python -m gate_scanner.main --universe RELIANCE TCS HDFCBANK INFY SBIN

# Custom timeframes
python -m gate_scanner.main --timeframes 60m 1d 1wk

# Full NSE + BSE universe (~1,900 stocks)
python -m gate_scanner.main --all-stocks

# Show detailed reasoning panel for specific stocks
python -m gate_scanner.main --detail RELIANCE HDFCBANK

# Adjust parallel workers (default: 8)
python -m gate_scanner.main --workers 12

# Custom output directory
python -m gate_scanner.main --out ./my_output

# Quiet mode (suppress INFO logs)
python -m gate_scanner.main --quiet
```

### 2. Daily EOD Scan (Recommended)

Optimized for end-of-day use after market close (3:30 PM IST). Scans only the daily timeframe for faster execution:

```bash
# Full default universe
python -m gate_scanner.daily_scanner

# F&O stocks only (higher liquidity)
python -m gate_scanner.daily_scanner --fno-only

# Include smallcap stocks
python -m gate_scanner.daily_scanner --include-smallcap

# Full NSE + BSE universe
python -m gate_scanner.daily_scanner --all-stocks
```

You can also run the daily scan via `main.py`:

```bash
python -m gate_scanner.main --mode daily
python -m gate_scanner.main --mode daily --fno-only
```

### 3. Backtesting

Run walk-forward backtests to validate the strategy on historical data:

```bash
# Default backtest (Nifty 50 + Next 50, from 2020-01-01)
python -m gate_scanner.main --mode backtest

# Custom date range
python -m gate_scanner.main --mode backtest --backtest-start 2021-01-01 --backtest-end 2024-12-31

# Custom universe
python -m gate_scanner.main --mode backtest --universe RELIANCE TCS HDFCBANK

# F&O stocks only
python -m gate_scanner.main --mode backtest --fno-only

# Custom starting capital (default: ₹10,00,000)
python -m gate_scanner.main --mode backtest --backtest-capital 500000
```

**Backtest features:**
- **Walk-forward simulation** — only data up to each simulation day is visible (no look-ahead)
- **Realistic fills** — entry at next bar's open price
- **Exit ladder** — SL hit → exit at SL; T1 → trail to breakeven; T2 → trail to T1; T3 → full exit
- **Position sizing** — 5% of equity per trade, max 10 concurrent positions
- **Reports** — HTML dashboard + 3 CSVs + per-trade Plotly charts in `gate_output/backtest/`

### 4. Automated Scheduling

Set up an automated post-market scan that runs Mon–Fri after market close:

```bash
# Default: runs at 4:00 PM IST, Mon–Fri
python -m gate_scanner.scheduler

# Custom time
python -m gate_scanner.scheduler --time 16:30

# F&O stocks only
python -m gate_scanner.scheduler --fno-only
```

> **Note:** Requires `apscheduler` — install with `pip install apscheduler>=3.10`

**Alternative: Use system cron (Linux/macOS):**

```bash
# Add to crontab (runs Mon–Fri at 4 PM IST / 10:30 UTC)
30 10 * * 1-5  /path/to/venv/bin/python -m gate_scanner.daily_scanner
```

**Alternative: Use Task Scheduler (Windows):**

Create a scheduled task that runs:
```
python -m gate_scanner.daily_scanner
```

---

## Output Files

Every scan generates the following files:

| File | Format | Description |
|------|--------|-------------|
| `signals.csv` | CSV | Machine-readable signal data — importable into Excel, Google Sheets, or any analysis tool |
| `signals.json` | JSON | Full signal data with nested objects — ideal for programmatic consumption |
| `scan_report.html` | HTML | Self-contained interactive report with dark theme, sortable tables, and embedded charts |
| `charts/<SYMBOL>_<TF>.html` | HTML | Per-signal Plotly candlestick charts with EMA/level overlays (linked from the main report) |

**Default output directories:**
- Full scan: `./gate_output/`
- Daily scan: `./gate_output/daily/`
- Backtest: `./gate_output/backtest/`

---

## Project Structure

```
gate-scanner/
├── README.md                         # ← You are here
├── GATE_Strategy.md                  # Full GATE trading strategy documentation
├── CLAUDE.md                         # AI assistant configuration
├── requirements.txt                  # Python dependencies
│
├── gate_scanner/                     # Main package
│   ├── __init__.py
│   ├── main.py                       # CLI entry point & pipeline orchestration
│   ├── daily_scanner.py              # Daily-timeframe-only scan mode
│   ├── scheduler.py                  # Automated post-market scheduler
│   ├── config.py                     # All tunable constants (weights, thresholds, rules)
│   │
│   ├── agents/                       # Pipeline stage agents
│   │   ├── __init__.py
│   │   ├── scanner_agent.py          # Stage 1: Data fetching & liquidity filter
│   │   ├── mtf_agent.py              # Stage 2: Multi-timeframe analysis
│   │   ├── risk_agent.py             # Stage 3: Signal building & risk checks
│   │   ├── ranking_agent.py          # Stage 4: Scoring & classification
│   │   └── report_agent.py           # Stage 5: Report generation
│   │
│   ├── ema_engine.py                 # EMA stack analysis, correction depth, bounce validation
│   ├── contraction_engine.py         # 6-component GATE score computation
│   ├── structure_engine.py           # Trend direction, phase detection, correction type
│   ├── signal_engine.py              # Entry/SL/target calculation, confidence, quality flags
│   ├── multi_timeframe.py            # MTF alignment, leading/confirmation TF detection
│   ├── ranking_engine.py             # Composite rank score formula
│   ├── classifier.py                 # Category classification logic
│   ├── indicators.py                 # Technical indicators (EMA, ATR, BB, ADX, Fibonacci)
│   ├── data_fetcher.py               # yfinance wrapper with Parquet disk cache
│   ├── reporting.py                  # Console & file output (CSV, JSON)
│   ├── charting.py                   # Plotly interactive chart builder
│   ├── scan_report.py                # HTML report generator (dark theme)
│   │
│   ├── universe/                     # Stock universe management
│   │   ├── __init__.py
│   │   ├── nse_universe.py           # NSE/BSE symbol lists (static + live fetch)
│   │   └── filters.py                # Universe filtering (sector, F&O, exclude list)
│   │
│   └── backtester/                   # Walk-forward backtesting engine
│       ├── __init__.py
│       ├── engine.py                 # Backtest simulation loop
│       ├── portfolio.py              # Portfolio & position management
│       ├── trade.py                  # Trade object model
│       ├── metrics.py                # Performance metrics (CAGR, Sharpe, drawdown)
│       └── report.py                 # Backtest HTML report + equity curves
│
├── gate_output/                      # Scan results (auto-generated)
│   ├── signals.csv
│   ├── signals.json
│   ├── scan_report.html
│   ├── charts/                       # Per-signal interactive charts
│   ├── daily/                        # Daily scanner output
│   └── backtest/                     # Backtester output
│
└── .gate_cache/                      # Disk cache (auto-generated)
    ├── *.parquet                      # Cached OHLCV data (1h TTL)
    └── *.txt                          # Cached universe lists (24h TTL)
```

---

## Configuration Reference

All tunable parameters are centralized in [`config.py`](gate_scanner/config.py). No magic numbers exist in the engine files.

### GATE Detection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BB_SQUEEZE_PERCENTILE` | 20 | BB width percentile threshold (bottom N%) |
| `ATR_SQUEEZE_PERCENTILE` | 25 | ATR percentile threshold |
| `EMA_COMPRESSION_THRESHOLD` | 0.04 (4%) | Max EMA spread / price for "compressed" |
| `NR_LOOKBACK` | 5 | Narrow range candle lookback |
| `VOL_CONTRACTION_LOOKBACK_SHORT` | 10 | Short volume MA window |
| `VOL_CONTRACTION_LOOKBACK_LONG` | 50 | Long volume MA window |
| `ADX_CONTRACTION_WEAK` | 15 | ADX ≤ this = full contraction score |
| `ADX_CONTRACTION_STRONG` | 35 | ADX ≥ this = zero contraction score |

### GATE Score Weights (must sum to 1.0)

| Component | Weight |
|-----------|--------|
| `bb_squeeze` | 22% |
| `atr_contraction` | 18% |
| `ema_compression` | 22% |
| `narrow_range` | 13% |
| `volume_contract` | 13% |
| `adx_contraction` | 12% |

### Risk Filters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_RR_RATIO` | 1.5 | Minimum risk-reward at T1 |
| `MIN_PRICE` | ₹20 | Penny stock filter |
| `MIN_AVG_VOLUME` | 100,000 | 20-day avg volume floor |
| `MAX_SL_DISTANCE_PCT` | 12% | Maximum SL distance from entry |

### Rank Score Weights

| Component | Weight |
|-----------|--------|
| `gate_strength` | 30% |
| `mtf_alignment` | 25% |
| `structure_quality` | 20% |
| `breakout_probability` | 15% |
| `rr_ratio` | 10% |

### Backtester Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BACKTEST_START_DATE` | 2020-01-01 | Simulation start |
| `BACKTEST_CAPITAL` | ₹10,00,000 | Starting capital |
| `BACKTEST_POSITION_PCT` | 5% | Per-trade equity allocation |
| `BACKTEST_MAX_POSITIONS` | 10 | Max concurrent positions |
| `BACKTEST_TIMEFRAME` | 1d | Timeframe for backtest |

---

## Column Reference

> Complete field-by-field guide to every column in the scanner report.

### Quick Reference Table

| Column | What It Measures | Range | Minimum to Pass |
|--------|-----------------|-------|-----------------:|
| **Symbol** | NSE / BSE ticker | — | — |
| **TF** | Confirmation timeframe | 1m → 1mo | — |
| **Action** | Trade direction | BUY / SELL | — |
| **Phase** | Market phase | 4 states | — |
| **Entry** | Suggested entry price (INR) | > ₹20 | ₹20 price floor |
| **SL** | Stop-loss price (INR) | < Entry | SL distance ≤ 12% |
| **T1 / T2 / T3** | Profit targets (INR) | > Entry | — |
| **RR(T2)** | Risk-reward ratio at T2 | ≥ 1.5x | RR(T1) ≥ 1.5x |
| **GATE** | Volatility contraction score | 0 – 100 | ≥ 55 for signal |
| **Conf%** | Signal confidence | 0 – 100 | — |
| **MTF%** | % of timeframes aligned | 0 – 100 | — |
| **HTF** | Higher-TF confirms direction | Yes / No | — |
| **Score** | Final rank score | 0 – 100 | Varies by category |
| **Reasoning** | Auto-generated narrative | — | — |

---

### Symbol

The exchange ticker for the stock.

- **NSE stocks** — shown as-is (e.g., `RELIANCE`, `TCS`)
- **BSE-only stocks** — shown with `.BO` suffix (e.g., `ZENSARTECH.BO`)
- **Symbols with special characters** — `M&M`, `BAJAJ-AUTO` are normalised internally when passed to yfinance

---

### TF — Timeframe

The **confirmation timeframe** where the trade signal is generated. This is always one step *higher* than the **leading timeframe** (the smallest TF where the GATE is actively forming).

**Timeframe hierarchy (smallest to largest):**

```
1m  ->  3m  ->  5m  ->  15m  ->  30m  ->  60m  ->  4h  ->  1d  ->  1wk  ->  1mo
```

> The `4h` timeframe is synthesised from 60m bars because yfinance has no native 4h interval.

**How the signal TF is chosen:**
1. The scanner finds the **leading TF** = smallest TF with GATE ≥ 55 *or* breakout probability ≥ 60
2. The **confirmation TF** = the next-larger TF in the hierarchy
3. If the confirmation TF agrees on direction, the signal is generated on the confirmation TF

**Example:**
- 60m chart shows GATE = 62 (leading TF = `60m`)
- 4h chart also shows bullish EMA stack (confirmation TF = `4h`)
- Signal TF column shows **4h**

---

### Action

The trade direction derived from a majority vote across three sources per timeframe:

| Vote Source | BUY signal when | SELL signal when |
|-------------|-----------------|------------------|
| EMA Stack | EMA20 > EMA50 > EMA100 > EMA200 | EMA20 < EMA50 < EMA100 < EMA200 |
| Trend (slope) | EMA50 slope > 0 AND EMA100 slope > 0 | Both slopes negative |
| GATE Bias | Last close > mid Bollinger Band | Last close < mid Bollinger Band |

Dominant direction across all analysed timeframes determines the final action.

---

### Phase

The current market phase of the **signal timeframe**, identified by `structure_engine.py`:

| Phase | Meaning | Best Next Step |
|-------|---------|----------------|
| `contracting` | EMA spread < 4% of price AND tightening — a GATE is forming | **Watch closely** — entry is near |
| `correcting` | Price pulling back to an EMA or ranging sideways (time correction) | Wait for bounce confirmation |
| `trending` | Strong directional move: EMA50+EMA100 slopes aligned, ADX ≥ 25 | May be late to enter; trail stop |
| `transitioning` | Between phases — no dominant state | Lower confidence; reduce size |

**Phase detection logic:**

```
if EMA_spread < 4% AND tightening  ->  contracting
else if price_correction OR time_correction  ->  correcting
else if trend_strength >= 35 AND direction != range  ->  trending
else  ->  transitioning
```

---

### Entry

```
Entry = Close[-1]  of the signal (confirmation) timeframe
```

The entry is the **current market price** — no artificial markup is added.

**Constraint:** Entry < ₹20 → signal is rejected (penny-stock filter).

**Example:**
```
RELIANCE closing on the 1d chart at ₹2,847.30
→ Entry = ₹2,847.30
```

---

### SL — Stop Loss

The stop loss is anchored to the **EMA200 of the next-smaller timeframe** relative to the signal TF.
This keeps the SL aligned with the structural support level one degree lower.

**SL Timeframe Map (`config.SL_TIMEFRAME_MAP`):**

| Signal TF | SL computed from |
|-----------|------------------|
| 1mo | 1wk EMA200 |
| 1wk | 1d EMA200 |
| **1d** | **4h EMA200** |
| 4h | 60m EMA200 |
| 60m | 15m EMA200 |
| 30m | 15m EMA200 |
| 15m | 5m EMA200 |
| 5m | 3m EMA200 |
| 3m | 1m EMA200 |

**ATR fallback** (used when smaller-TF data is unavailable or SL is on the wrong side):

```
SL_BUY  = Entry - 2 × ATR(14)
SL_SELL = Entry + 2 × ATR(14)
```

**Hard filter — signal is rejected if:**

```
|Entry - SL| / Entry  >  12%
```

**Example:**

```
Signal TF = 1d  →  SL TF = 4h
4h EMA200 = ₹2,690
SL distance = |2847 - 2690| / 2847 = 5.5%  (passes 12% filter)
SL = ₹2,690.00
```

---

### T1 / T2 / T3 — Profit Targets

Targets combine an **ATR projection** (near target) with the **strategy expectancy table**
(medium and far targets), then snap to swing structure where applicable.

**Formula:**

```
# BUY
T1 = max( Entry + 2 × ATR(14),  Entry × (1 + low_pct × 0.25) )
T2 = Entry × (1 + mid_pct)
T3 = Entry × (1 + high_pct)
mid_pct = (low_pct + high_pct) / 2

# SELL (mirrored)
T1 = min( Entry - 2 × ATR(14),  Entry × (1 - low_pct × 0.25) )
T2 = Entry × (1 - mid_pct)
T3 = Entry × (1 - high_pct)
```

**Expectancy Table (`config.TARGET_EXPECTANCY`):**

| TF | low_pct | high_pct | Typical T2 move |
|----|---------|----------|:---------------:|
| 1mo | 800% | 1200% | ~1000% (multi-year) |
| 1wk | 200% | 300% | ~250% (1–2 years) |
| **1d** | **50%** | **70%** | **~60% (6–12 months)** |
| 4h | 35% | 40% | ~37.5% |
| 60m | 20% | 25% | ~22.5% |
| 30m | 10% | 15% | ~12.5% |
| 15m | 7% | 10% | ~8.5% |
| 5m | 5% | 7% | ~6% |
| 3m / 1m | 3% | 4% | ~3.5% |

**Structural snap rule:** If a swing high (BUY) lies between T1 and T2, T1 is snapped to that swing high — structural resistance is the most realistic near-term target.

**Example (1d BUY):**

```
Entry = ₹2,847   ATR(14) = ₹52   low_pct = 0.50   high_pct = 0.70
mid_pct = 0.60

T1 = max(2847 + 104,  2847 × 1.125) = max(2951, 3203) = ₹3,203
T2 = 2847 × 1.60 = ₹4,555
T3 = 2847 × 1.70 = ₹4,839
```

---

### RR(T2) — Risk-Reward at T2

```
# BUY
RR(T2) = (T2 - Entry) / (Entry - SL)

# SELL
RR(T2) = (Entry - T2) / (SL - Entry)
```

**Hard filter:** If `RR(T1) < 1.5`, the signal is **rejected entirely**.

**Example:**

```
Entry = ₹2,847   SL = ₹2,690   T2 = ₹4,555
RR(T2) = (4555 - 2847) / (2847 - 2690)
       = 1708 / 157
       = 10.9x
```

---

### GATE — Volatility Contraction Score

The GATE score measures how tightly compressed a stock is before an expansion move.
Six independent contraction signals are each scored 0–1, then combined:

```
GATE = 100 × sum( component_score[i] × weight[i] )
```

**Components and Weights:**

| # | Component | Weight | Score = 1.0 when |
|---|-----------|:------:|------------------|
| 1 | **BB Squeeze** | 22% | BB width at the 0th percentile of last 100 bars |
| 2 | **ATR Contraction** | 18% | ATR(14) at the 0th percentile of last 100 bars |
| 3 | **EMA Compression** | 22% | (EMA_max - EMA_min) / price = 0 |
| 4 | **Narrow Range** | 13% | Avg range of last 5 candles = 0 vs ATR |
| 5 | **Volume Contraction** | 13% | 10-bar vol avg = 40% of 50-bar vol avg |
| 6 | **ADX Contraction** | 12% | ADX(14) = 0 |

<details>
<summary><strong>Component Score Formulas (click to expand)</strong></summary>

```
# 1. BB Squeeze  (bottom-20th-percentile trigger)
pct   = rank of current_bb_width in last 100 bars (%)
score = 1.0 - pct/20   if pct <= 20,  else 0.0

# 2. ATR Contraction  (bottom-25th-percentile trigger)
pct   = rank of current_atr in last 100 bars (%)
score = 1.0 - pct/25   if pct <= 25,  else 0.0

# 3. EMA Compression
spread = (max(EMA20, EMA50, EMA100, EMA200) - min(...)) / Close
score  = max(0,  1 - spread / 0.08)

# 4. Narrow Range
ratio = mean_range_last5_bars / ATR(14)
score = max(0, min(1,  (1 - ratio) / 0.4))   if ratio < 1.0,  else 0.0

# 5. Volume Contraction
ratio = vol_10bar_mean / vol_50bar_mean
score = max(0, min(1,  (1 - ratio) / 0.6))   if ratio < 1.0,  else 0.0

# 6. ADX Contraction   (weak=15, strong=35)
score = 1.0                              if ADX <= 15
score = 0.0                              if ADX >= 35
score = 1 - (ADX - 15) / (35 - 15)      otherwise
```

</details>

**GATE Classification:**

| GATE Score | Interpretation |
|:----------:|----------------|
| ≥ 70 | 🟢 **Strong GATE** — high-conviction compression |
| 55 – 70 | 🟡 **Active GATE** — valid setup; signal generated |
| < 55 | ⚪ Sub-threshold — monitored, no trade signal |

**Example calculation:**

```
BB=0.85  ATR=0.72  EMA=0.90  NR=0.60  Vol=0.55  ADX=0.80

GATE = 100 × (0.85×0.22 + 0.72×0.18 + 0.90×0.22 + 0.60×0.13 + 0.55×0.13 + 0.80×0.12)
     = 100 × (0.187 + 0.130 + 0.198 + 0.078 + 0.072 + 0.096)
     = 100 × 0.761
     = 76.1  →  Strong GATE ✅
```

---

### Conf% — Confidence

A composite quality score combining signal strengths with structural quality flags.

**Base Formula:**

```
base = 0.30 × GATE_score
     + 0.25 × MTF_alignment_pct
     + 0.20 × Structure_Quality
     + 0.25 × Breakout_Probability
```

**Multiplier Adjustments:**

| Condition | Change |
|-----------|--------|
| HTF confirmed | +10% |
| Fake correction (EMA200 not touched in last pullback) | -10% |
| Bounce sequence invalid (EMA levels skipped) | -8% |
| Fibonacci confluence at correction level | +8% |

```
Conf% = min(100,  base × multiplier)
```

<details>
<summary><strong>Structure Quality & Breakout Probability formulas (click to expand)</strong></summary>

**Structure Quality:**
```
SQ = 0.40 × StackScore
   + 0.35 × TrendStrength
   + 0.25 × EMA_Respect

StackScore    = 100  if stack is purely bullish or bearish
              = 40   if stack is mixed
TrendStrength = min(100, ADX(14) × 1.5)
EMA_Respect   = max(0, min(100,  100 × (1 - mean_dev / 0.10)))
                mean_dev = mean(|Close - EMA50| / EMA50)  over last 20 bars
```

**Breakout Probability:**
```
BP = min(100, GATE × vol_factor × struct_factor)

vol_factor    = 1.0 + clamp(-0.20, +0.30,  (vol_3bar / vol_20bar - 1) × 0.5)
struct_factor = 1.1  if stack is purely bullish/bearish,  else 0.9
```

</details>

---

### MTF% — Multi-Timeframe Alignment

```
MTF% = (TFs pointing in dominant direction / total TFs with data) × 100
```

Each TF casts three votes (EMA stack / slope direction / GATE bias). A 2-of-3 majority sets that TF's direction.

**Example:**

```
TFs: 60m=up, 4h=up, 1d=up, 1wk=up, 1mo=down
MTF% = 4/5 × 100 = 80%
```

---

### HTF — Higher Timeframe Confirmation

```
Leading TF      = smallest TF with GATE >= 55 OR breakout_prob >= 60
Confirmation TF = next-larger TF in the 10-level hierarchy

HTF = Yes  if direction(leading_TF) == direction(confirmation_TF) != neutral
HTF = No   otherwise
```

HTF = Yes adds an **8% bonus** to the final rank Score.

---

### Score — Rank Score

```
Score = (  0.30 × GATE_score
         + 0.25 × MTF_pct
         + 0.20 × Structure_Quality
         + 0.15 × Breakout_Probability
         + 0.10 × RR_norm  )
        × (1.08  if HTF_confirmed  else  1.0)

RR_norm = min(RR_T2 / 5.0,  1.0) × 100   # capped at RR=5x, scaled to 0-100
```

**Category thresholds:**

| Category | Min Score |
|----------|:---------:|
| INVESTMENT | ≥ 70 |
| SWING | ≥ 60 |
| POSITIONAL | ≥ 50 |
| WATCH | — |

---

### Reasoning

An auto-generated narrative covering:

1. EMA stack state and current phase
2. GATE component breakdown (if GATE ≥ 55)
3. Correction type and depth (price vs time; which EMA is tested)
4. Quality warnings (fake correction / skipped EMA bounce sequence)
5. Fibonacci confluence (38.2 / 50 / 61.8% retracement alignment)
6. Correction maturity (bars elapsed vs expected duration for the TF)
7. MTF alignment summary and HTF status

---

## Signal Categories

| Category | Classification Rules |
|----------|---------------------|
| **INVESTMENT** | Weekly AND monthly EMA bullish · Score ≥ 70 |
| **SWING** | Daily EMA bullish · Daily GATE ≥ 60 · Score ≥ 60 |
| **POSITIONAL** | 60m EMA bullish · 60m GATE ≥ 50 · Score ≥ 50 |
| **WATCH** | Best GATE across any TF ≥ 55 but no confirmed breakout yet |
| **IGNORE** | Bearish across weekly/monthly/daily, or RR below threshold |

Classification is top-down — the first matching rule wins.

---

## Signal Quality Flags

### Correction Validated

Checks whether the most recent pullback actually touched EMA200 before reversing.

```
Validated = True   if any bar in the correction window had:
              Low within 3% of EMA200 from above  OR  Close <= EMA200
Validated = False  →  Conf% - 10%  + warning in Reasoning
```

### Bounce Sequence Valid

The GATE Strategy expects successive corrections to step through EMA levels in order:
**EMA20 → EMA50 → EMA100 → EMA200**. Jumping straight to a deeper EMA is higher-risk.

```
Valid = True   if all prior required EMAs were touched within the last 500 bars
              (tolerance = 3% = 2 × EMA_TOUCH_TOLERANCE)
Valid = False  →  Conf% - 8%  + warning in Reasoning
```

---

## Worked Example End-to-End

**Stock:** HDFC Bank (HDFCBANK) · Scan date: 2026-05-28 · Signal TF: 1d

| Step | Calculation | Result |
|------|-------------|--------|
| Leading TF | 1d GATE = 68 ≥ 55 | `1d` |
| Confirmation TF | Next-larger = 1wk; 1wk direction = up | Confirmed |
| Entry | 1d Close | ₹1,742.00 |
| SL TF | 1d → 4h (SL_TIMEFRAME_MAP) | 4h EMA200 |
| SL | 4h EMA200 | ₹1,628.00 |
| SL distance | (1742-1628)/1742 | 6.5% ✅ |
| ATR(14) | 1d bar average true range | ₹28 |
| T1 | max(1742+56, 1742×1.125) | ₹1,960 |
| T2 | 1742 × 1.60 | ₹2,787 |
| T3 | 1742 × 1.70 | ₹2,961 |
| RR(T1) | (1960-1742)/(1742-1628) | 1.9x ✅ |
| RR(T2) | (2787-1742)/(1742-1628) | 9.2x |
| GATE | Weighted 6-component score | 68.4 (Active GATE) |
| MTF% | 4 of 5 TFs aligned up | 80% |
| HTF | 1wk agrees with 1d | Yes |
| Conf% base | 0.30×68.4+0.25×80+0.20×70+0.25×64 | 70.5 |
| Conf% final | 70.5 × 1.10 (HTF bonus) | **77.6%** |
| Score | (0.30×68.4+0.25×80+0.20×70+0.15×64+0.10×100) × 1.08 | **78.2** |
| Category | Weekly+monthly bullish, Score ≥ 70 | **INVESTMENT** |

---

## FAQ & Troubleshooting

<details>
<summary><strong>How long does a scan take?</strong></summary>

| Mode | Universe Size | Approx. Time |
|------|:------------:|:------------:|
| Quick test (3 stocks) | 3 | ~30 seconds |
| Daily scan (default) | ~700 | ~5–8 minutes |
| Full MTF scan (default) | ~700 | ~15–25 minutes |
| All stocks | ~1,900 | ~30–60 minutes |

Times depend on your internet speed and yfinance rate limits.

</details>

<details>
<summary><strong>I'm getting "No data found" errors for some stocks</strong></summary>

This is normal. Some stocks may be recently listed, suspended, or have ticker changes. The scanner logs a warning and skips them. The liquidity filter (price ≥ ₹20, avg volume ≥ 1L) will also filter out illiquid names.

</details>

<details>
<summary><strong>Can I use this for intraday trading?</strong></summary>

Yes, but note the yfinance data limitations:
- **1m / 3m data** — only 7 days of history available
- **5m / 15m / 30m data** — only 60 days of history
- **60m data** — 730 days

For intraday, use the full MTF scan (`python -m gate_scanner.main`) which includes shorter timeframes by default.

</details>

<details>
<summary><strong>How do I add my own stocks to the scan?</strong></summary>

Use the `--universe` flag:

```bash
python -m gate_scanner.main --universe RELIANCE TCS HDFCBANK INFY SBIN
```

Or programmatically:

```python
from gate_scanner.main import run_scan
results = run_scan(universe=["RELIANCE", "TCS", "HDFCBANK"])
```

</details>

<details>
<summary><strong>How do I filter by sector?</strong></summary>

Use the `UniverseFilter` class:

```python
from gate_scanner.universe import UniverseFilter, get_full_universe

symbols = (
    UniverseFilter(get_full_universe())
    .by_sector(["Banking"])
    .exclude(["PAYTM"])
    .get()
)
```

</details>

<details>
<summary><strong>Can I use a different data source instead of yfinance?</strong></summary>

Yes. Only `data_fetcher._fetch_yf()` and `get_bulk_history()` need to change. The rest of the pipeline consumes standard `DatetimeIndex` OHLCV DataFrames with columns `Open/High/Low/Close/Volume`.

</details>

<details>
<summary><strong>Symbols like M&M or BAJAJ-AUTO aren't working</strong></summary>

These are normalised internally by `data_fetcher.py`, but yfinance can be finicky with special characters. If a specific symbol fails, try passing it with the `.NS` suffix explicitly: `M%26M.NS`.

</details>

<details>
<summary><strong>How do I clear the cache?</strong></summary>

Delete the `.gate_cache/` directory:

```bash
# Windows
rmdir /s /q .gate_cache

# macOS / Linux
rm -rf .gate_cache
```

Or set a custom cache location via the `GATE_CACHE_DIR` environment variable.

</details>

---

## Contributing

1. **Fork** the repository
2. **Create a feature branch** (`git checkout -b feature/my-feature`)
3. **Make your changes** — all tunable constants go in `config.py`, not in engine files
4. **Test manually** — there is no automated test suite yet. Run the scanner and verify output.
5. **Submit a pull request** with a clear description of your changes

### Code Conventions

- All technical indicators are implemented in `indicators.py` — no external TA libraries required
- Engine files import from `indicators.py` and `config.py` only
- Console output uses `rich` library (falls back to plain text if not installed)
- Charts use `plotly` with embedded JS for offline viewing

---

## Disclaimer

> **⚠️ This tool is for educational and research purposes only.** It does not constitute financial advice. Trading in the stock market involves risk of loss. Past performance (including backtester results) does not guarantee future returns. Always do your own research and consult a qualified financial advisor before making investment decisions.

---

<div align="center">

**Built with ❤️ for the Indian trading community**

*GATE Strategy: Master the correction — and the trend will take care of itself.*

</div>
