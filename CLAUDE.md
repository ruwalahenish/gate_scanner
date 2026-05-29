# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install apscheduler   # required for scheduler only

# Full multi-timeframe scan (default universe: Nifty 50 + Next 50 + Midcap 150 + F&O)
python -m gate_scanner.main

# Custom universe or detail panel + signal chart for a symbol
python -m gate_scanner.main --universe RELIANCE TCS HDFCBANK --detail RELIANCE

# Full NSE + BSE universe (~1900 symbols; fetches live symbol list, cached 24 h)
python -m gate_scanner.main --all-stocks

# EOD daily-timeframe scan (recommended for most use)
python -m gate_scanner.daily_scanner
python -m gate_scanner.daily_scanner --fno-only
python -m gate_scanner.daily_scanner --include-smallcap
python -m gate_scanner.daily_scanner --all-stocks

# Same modes via main.py --mode flag
python -m gate_scanner.main --mode daily
python -m gate_scanner.main --mode backtest --backtest-start 2021-01-01

# Backtester
python -m gate_scanner.main --mode backtest
python -m gate_scanner.main --mode backtest --universe RELIANCE TCS --backtest-start 2021-01-01

# Automated post-market scheduler (blocks; fires Mon–Fri at 4 PM IST)
python -m gate_scanner.scheduler
python -m gate_scanner.scheduler --time 16:30 --fno-only
```

There is no test suite or linter configured. Run modules directly to verify behaviour.

## Architecture

The scanner is a **5-stage sequential pipeline** in `main.py:run_scan()`:

```
MarketScannerAgent  →  MTFAnalysisAgent  →  RiskManagementAgent  →  SignalRankingAgent  →  ReportGenerationAgent
    fetch + filter       per-TF engines        signal + RR check        rank + classify         console/CSV/JSON/HTML
```

### Stage 1 — Scanner Agent (`agents/scanner_agent.py`)
Parallel-fetches all symbols via `ThreadPoolExecutor` using `as_completed` (real-time terminal output per symbol). Filters on price ≥ ₹20 and 20-day avg volume ≥ 100k. Returns `{ symbol: { tf: DataFrame } }`.

### Stage 2 — MTF Analysis Agent (`agents/mtf_agent.py` → `multi_timeframe.py`)
For each symbol runs three engines per timeframe:
- `ema_engine.py` — EMA stack state (bullish/bearish/mixed), correction depth, bounce sequence
- `contraction_engine.py` — 6-component GATE score (0–100); ≥55 = GATE, ≥70 = strong GATE
- `structure_engine.py` — trend direction, correction type (price/time), phase, correction age %

Then `mtf_summary()` identifies the **leading TF** (smallest with GATE or breakout_prob ≥ 60) and **confirmation TF** (next-larger agreeing TF). MTF alignment % and HTF confirmation bonus are computed here.

### Stage 3 — Risk Agent (`agents/risk_agent.py` → `signal_engine.py`)
Builds the concrete signal on the **confirmation TF** (not leading TF):
- **Entry** = current close of signal TF
- **SL** = EMA200 of the *smaller* TF (defined in `config.SL_TIMEFRAME_MAP`)
- **Targets T1/T2/T3** = ATR-projected, anchored to `config.TARGET_EXPECTANCY`, clamped to swing highs/lows
- **Confidence** = composite ± penalties for fake correction / invalid bounce sequence ± Fibonacci confluence boost

Hard filters: RR(T1) ≥ 1.5, SL distance ≤ 12%.

### Stage 4 — Ranking & Classification (`agents/ranking_agent.py`)
Computes `rank_score` (0–100) using `config.RANK_WEIGHTS`. Classifies into INVESTMENT / SWING / POSITIONAL / WATCH / IGNORE via `classifier.py` based on `config.CATEGORY_RULES`. Sorts output by category priority then rank score descending.

### Stage 5 — Report Agent (`agents/report_agent.py` → `reporting.py`)
Prints a rich console table grouped by category. Writes to the output directory:
- `signals.csv` and `signals.json` — machine-readable signal data
- `scan_report.html` — self-contained interactive HTML report (dark theme, sortable tables; built by `scan_report.py`)
- `charts/<SYMBOL>_<TF>.html` — per-signal Plotly candlestick charts with EMA/level overlays (built by `charting.py`; linked from `scan_report.html`)

Uses `rich` library for console output if installed; falls back to plain text.

## Supporting Modules

- **`indicators.py`** — pure-pandas/numpy technical indicators (EMA, ATR, Bollinger Bands, ADX, Fibonacci levels). No external TA library required; all engines import from here.
- **`charting.py`** — Plotly interactive charts: `build_signal_chart()` for live signals, `build_trade_chart()` for backtest trades, `build_equity_chart()` for equity/drawdown curves. Embeds `plotly.min.js` from the local package (offline-capable) with CDN fallback via `get_plotly_js_tag()`.

## Key Design Decisions

**`4h` timeframe is synthesized** — yfinance has no native 4h interval; `data_fetcher.py` resamples 60m bars. The `MarketScannerAgent` always fetches `4h` because `SL_TIMEFRAME_MAP["1d"] = "4h"` — daily signals need 4h EMA200 for the stop loss.

**Monthly blue-chip exception** — On the monthly timeframe, stocks in `config.NIFTY_50` correct to EMA100, not EMA200. This is enforced in `ema_engine.analyze()` when `timeframe="1mo"` and the symbol is a blue-chip. Both `symbol` and `timeframe` must be passed through to `analyze_timeframe()` for this to work.

**Disk cache** — Fetched data is cached in `.gate_cache/` as Parquet files with a 1-hour TTL (`data_fetcher.CACHE_TTL_SECONDS`). Universe lists (NSE/BSE) are cached as `.txt` files with a 24-hour TTL. Override cache location with `GATE_CACHE_DIR` env var.

**All tunables in `config.py`** — No magic numbers exist in the engine files. GATE score weights (`GATE_WEIGHTS`), rank weights (`RANK_WEIGHTS`), classification thresholds (`CATEGORY_RULES`), SL mapping (`SL_TIMEFRAME_MAP`), and target expectancy (`TARGET_EXPECTANCY`) are all centralised there.

**Swapping the data source** — Only `data_fetcher._fetch_yf()` and `get_bulk_history()` need to change. The rest of the pipeline consumes standard `DatetimeIndex` OHLCV DataFrames with columns `Open/High/Low/Close/Volume`.

## Universe

`nse_universe.get_full_universe()` returns ~700 deduplicated NSE symbols (Nifty 50/100/150, Smallcap 100, F&O eligible, BSE 100). Narrow it with `UniverseFilter`:

```python
from gate_scanner.universe import UniverseFilter, get_full_universe
symbols = UniverseFilter(get_full_universe()).by_sector(["Banking"]).exclude(["PAYTM"]).get()
```

Pass `live=True` to fetch the current Nifty 500 CSV from NSE India instead of the static list. Pass `all_equity=True` (or `--all-stocks` on the CLI) for the full NSE EQ-series (~1900 symbols) + BSE-only equities, fetched live and cached 24 h. BSE-only symbols are returned with a `.BO` suffix.

## Backtester Notes

Walk-forward in `backtester/engine.py` — only data up to each simulation day is visible (no look-ahead). Entry fills at next bar's open. Exit ladder: SL hit → exit at SL; T1 hit → trail to break-even; T2 hit → trail to T1; T3 hit → full exit. Position sizing is 5% of current equity (`BACKTEST_POSITION_PCT`), max 10 concurrent positions. Signal scan runs every 5 bars (`scan_interval=5`) since GATE setups persist for weeks. Outputs HTML report + 3 CSVs + per-trade Plotly charts to `gate_output/backtest/`.

## Caveats

- yfinance intraday history is limited: 7d for 1m/3m, 60d for 5–30m, 730d for 60m. Long intraday backtests require a different data source.
- Symbols with `&` (e.g. `M&M`, `BAJAJ-AUTO`) are normalised by `data_fetcher` but can be finicky with yfinance.
- GATE thresholds are calibrated for liquid Nifty names. For mid/small caps, consider relaxing `BB_SQUEEZE_PERCENTILE` and `MIN_AVG_VOLUME` in `config.py`.
