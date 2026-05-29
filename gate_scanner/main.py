"""
main.py
========
Orchestrates the full GATE scan:

    Scanner ─► MTF Analysis ─► Risk (signal build) ─► Ranking & Classify ─► Report

Run from project root:

    python -m gate_scanner.main
    python -m gate_scanner.main --universe RELIANCE TCS HDFCBANK
    python -m gate_scanner.main --timeframes 60m 1d 1wk --workers 4
"""

from __future__ import annotations

import argparse
import logging
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

from . import config
from .agents import (
    MarketScannerAgent,
    MTFAnalysisAgent,
    RiskManagementAgent,
    SignalRankingAgent,
    ReportGenerationAgent,
)

logger = logging.getLogger("gate_scanner")


def _best_gate(per_tf: Dict) -> float:
    scores = [
        v.get("gate", {}).get("score", 0)
        for v in per_tf.values()
        if isinstance(v, dict)
    ]
    return max(scores) if scores else 0.0


def run_scan(
    universe: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    workers: int = 8,
    out_dir: str = "./gate_output",
    detail_symbols: Optional[List[str]] = None,
    all_equity: bool = False,
):
    """
    Top-level entry point. Returns the full results list.

    Parameters
    ----------
    universe    : explicit symbol list; overrides all_equity when provided
    all_equity  : when True and universe is None, fetches all NSE EQ-series
                  equities (~1900) plus BSE-only stocks and uses that as the
                  universe.  Results are cached 24 h in .gate_cache/.
    """
    from .universe.nse_universe import get_full_universe

    t0 = time.time()

    # ---- Resolve universe ----
    if universe is None:
        universe = get_full_universe(
            include_midcap=True,
            include_smallcap=all_equity,   # include smallcap when doing full scan
            all_equity=all_equity,
        )

    # ---- 1) Scanner agent: universe + parallel fetch + liquidity prefilter ----
    scanner = MarketScannerAgent(
        universe=universe,
        timeframes=timeframes,
        max_workers=workers,
    )
    logger.info("Scanning %d symbols across %s", len(scanner.universe), scanner.timeframes)
    universe_data = scanner.scan()
    logger.info("  -> %d symbols passed liquidity filter", len(universe_data))

    # ---- 2) MTF Analysis agent: run engines on each TF ----
    mtf_agent = MTFAnalysisAgent()
    # ---- 3) Risk agent: build trade signals ----
    risk_agent = RiskManagementAgent()

    symbols_to_analyze = list(universe_data.items())
    total_analysis = len(symbols_to_analyze)
    print(f"\n  Analyzing {total_analysis} symbols...\n")

    enriched = []
    for ana_idx, (symbol, mtf_data) in enumerate(symbols_to_analyze, 1):
        try:
            mtf_result = mtf_agent.analyze(mtf_data, symbol=symbol)
            signal = risk_agent.build_signal(
                symbol,
                mtf_data,
                mtf_result["per_tf"],
                mtf_result["summary"],
            )
            if signal:
                gate  = signal.get("gate_strength", 0.0)
                tf    = signal.get("signal_timeframe", "?")
                side  = signal.get("side", "?")
                entry = signal.get("entry", 0.0)
                conf  = signal.get("confidence", 0.0)
                line  = f"GATE={gate:.1f}  {side} @ {tf}  entry=₹{entry:.2f}  conf={conf:.1f}"
            else:
                best_gate = _best_gate(mtf_result["per_tf"])
                line = f"GATE={best_gate:.1f}  no signal"
            print(f"  [Scan {ana_idx:3d}/{total_analysis}] {symbol:<22}  {line}")
            enriched.append({
                "symbol":      symbol,
                "mtf_per_tf":  mtf_result["per_tf"],
                "mtf_summary": mtf_result["summary"],
                "signal":      signal,
                "ohlcv":       mtf_data,   # raw DataFrames for charting
            })
        except Exception as e:
            print(f"  [Scan {ana_idx:3d}/{total_analysis}] {symbol:<22}  ERROR: {e}")
            logger.exception("analysis failed for %s: %s", symbol, e)

    # ---- 4) Ranking & classification ----
    ranker = SignalRankingAgent()
    results = ranker.rank_and_classify(enriched)

    cats = Counter(r["classification"]["category"] for r in results)
    parts = [
        f"{cats[c]} {c}"
        for c in ["INVESTMENT", "SWING", "POSITIONAL", "WATCH", "IGNORE"]
        if cats.get(c, 0) > 0
    ]
    print(f"\n  Ranked {len(results)} symbols: {',  '.join(parts)}\n")

    # ---- 5) Reporting ----
    reporter = ReportGenerationAgent(out_dir=out_dir)
    scan_meta = {
        "scan_time":     datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "universe_size": len(scanner.universe),
        "timeframes":    scanner.timeframes,
    }
    paths = reporter.render(results, detail_symbols=detail_symbols, scan_meta=scan_meta)

    dt = time.time() - t0
    logger.info("Done in %.1fs. CSV: %s  JSON: %s  HTML: %s", dt, paths["csv"], paths["json"], paths.get("html", ""))
    return results


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def _cli():
    parser = argparse.ArgumentParser(description="GATE Scanner — Indian market opportunity scanner")
    parser.add_argument(
        "--mode", choices=["scan", "daily", "backtest"], default="scan",
        help="scan = full MTF scan; daily = EOD daily-TF only; backtest = walk-forward simulation.",
    )
    parser.add_argument("--universe", nargs="+", default=None,
                        help="Stock symbols (NSE). Default varies by mode.")
    parser.add_argument("--timeframes", nargs="+",
                        default=["15m", "60m", "1d", "1wk", "1mo"],
                        help="yfinance interval strings (scan mode only).")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", default="./gate_output")
    parser.add_argument("--detail", nargs="*", default=None,
                        help="Symbols to print a detailed reasoning panel for (scan mode).")
    # Backtest options
    parser.add_argument("--backtest-start", default=config.BACKTEST_START_DATE,
                        help="Backtest start date YYYY-MM-DD (backtest mode).")
    parser.add_argument("--backtest-end", default=None,
                        help="Backtest end date YYYY-MM-DD (backtest mode, default=today).")
    parser.add_argument("--backtest-capital", type=float, default=config.BACKTEST_CAPITAL,
                        help="Starting capital in INR (backtest mode).")
    parser.add_argument("--fno-only", action="store_true",
                        help="Use only F&O eligible stocks (daily / backtest modes).")
    parser.add_argument(
        "--all-stocks", action="store_true",
        help=(
            "Scan every equity listed on NSE (EQ series, ~1900 symbols) and BSE. "
            "Fetches live symbol lists from NSE/BSE, cached for 24 h. "
            "The liquidity filter (price ≥ ₹20, 20-day avg vol ≥ 1L) still applies."
        ),
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.mode == "daily":
        from .daily_scanner import run_daily_scan
        run_daily_scan(
            universe=args.universe,
            out_dir=args.out,
            workers=args.workers,
            include_fno_only=args.fno_only,
            all_equity=args.all_stocks,
        )

    elif args.mode == "backtest":
        from .universe.nse_universe import get_full_universe
        from .backtester import BacktestEngine, compute_metrics, BacktestReport
        universe = args.universe or get_full_universe(include_fno_only=args.fno_only)
        engine = BacktestEngine(
            universe=universe,
            start_date=args.backtest_start,
            end_date=args.backtest_end,
            initial_capital=args.backtest_capital,
            workers=args.workers,
        )
        portfolio = engine.run()
        metrics   = compute_metrics(portfolio)
        report    = BacktestReport(
            portfolio, metrics,
            out_dir=args.out + "/backtest",
            history=engine.history,
        )
        paths     = report.render()
        logger.info(
            "Backtest complete. CAGR=%.1f%% Sharpe=%.2f MaxDD=%.1f%% Trades=%d",
            metrics["cagr"] * 100,
            metrics["sharpe_ratio"],
            metrics["max_drawdown"] * 100,
            metrics["total_trades"],
        )
        print(f"\nBacktest reports written to: {paths.get('html')}")

    else:
        run_scan(
            universe=args.universe,
            timeframes=args.timeframes,
            workers=args.workers,
            out_dir=args.out,
            detail_symbols=args.detail,
            all_equity=args.all_stocks,
        )


if __name__ == "__main__":
    _cli()
