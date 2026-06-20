"""
core/scanner/pipeline.py
=========================
Orchestrates the full GATE scan:

    Scanner ─► MTF Analysis ─► Risk (signal build) ─► Ranking & Classify ─► Report

This is the backend service entry point — no CLI, no argparse.
All execution is driven through backend APIs and Celery tasks.

Progressive streaming
---------------------
Pass an `on_batch` callable to receive results in chunks as they are produced,
rather than waiting for the full scan to complete:

    def on_batch(ranked_batch: list[dict], done: int, total: int) -> None:
        ...  # called after each batch of ~batch_size symbols is ranked

`on_batch` is called from inside the thread-pool worker (not the asyncio event
loop), so it must be thread-safe.  A common pattern is to push onto an
asyncio.Queue via run_coroutine_threadsafe (see scanner_tasks.py).
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Callable, Dict, List, Optional

from app.core import config
from app.agents import (
    MarketScannerAgent,
    MTFAnalysisAgent,
    RiskManagementAgent,
    SignalRankingAgent,
    ReportGenerationAgent,
)

logger = logging.getLogger("gate.scanner")

_BATCH_SIZE = 25          # symbols per progressive batch
_ANALYSIS_WORKERS = 8    # parallel threads for MTF+Risk analysis within each batch


def _best_gate(per_tf: Dict) -> float:
    scores = [
        v.get("gate", {}).get("score", 0)
        for v in per_tf.values()
        if isinstance(v, dict)
    ]
    return max(scores) if scores else 0.0


def _base_symbol(symbol: str) -> str:
    """Strip the BSE '.BO' suffix so stock_master / SECTOR_MAP lookups match."""
    return symbol[:-3] if symbol.endswith(".BO") else symbol


def _analyze_one(
    symbol: str,
    mtf_data: dict,
    mtf_agent: MTFAnalysisAgent,
    risk_agent: RiskManagementAgent,
    index_df=None,
    sector_momentum_map: Optional[Dict[str, float]] = None,
    fundamentals_map: Optional[Dict[str, dict]] = None,
) -> dict | None:
    """Analyze a single symbol through MTF + Risk stages. Returns enriched dict or None on error."""
    from app.core.analysis import relative_strength, fundamentals as fundamentals_mod
    from app.core.scanner.universe.nse_universe import SECTOR_MAP

    try:
        mtf_result = mtf_agent.analyze(mtf_data, symbol=symbol)

        base = _base_symbol(symbol)
        daily_df = mtf_data.get(config.SCAN_TIMEFRAME)
        rs = (
            relative_strength.rs_score(daily_df, index_df)
            if daily_df is not None and not daily_df.empty
            else config.RS_NEUTRAL
        )
        sector_mom = (sector_momentum_map or {}).get(
            SECTOR_MAP.get(base), config.SECTOR_NEUTRAL
        )
        fund = fundamentals_mod.fundamental_score(
            (fundamentals_map or {}).get(base)
        )

        signal = risk_agent.build_signal(
            symbol,
            mtf_data,
            mtf_result["per_tf"],
            mtf_result["summary"],
            rs_score=rs,
            sector_momentum=sector_mom,
            fundamental_score=fund,
        )
        return {
            "symbol":      symbol,
            "mtf_per_tf":  mtf_result["per_tf"],
            "mtf_summary": mtf_result["summary"],
            "signal":      signal,
            "ohlcv":       mtf_data,
        }
    except Exception as e:
        logger.exception("analysis failed for %s: %s", symbol, e)
        return None


def run_scan(
    universe: Optional[List[str]] = None,
    timeframes: Optional[List[str]] = None,
    workers: int = 8,
    out_dir: str = "./gate_output",
    detail_symbols: Optional[List[str]] = None,
    all_equity: bool = False,
    on_batch: Optional[Callable[[list, int, int], None]] = None,
    batch_size: int = _BATCH_SIZE,
    fundamentals_map: Optional[Dict[str, dict]] = None,
    on_phase: Optional[Callable[[str, str], None]] = None,
) -> List[Dict]:
    """
    Top-level scan entry point. Returns the full results list.

    Parameters
    ----------
    universe    : explicit symbol list; overrides all_equity when provided
    timeframes  : list of yfinance interval strings to scan
    workers     : parallel fetch workers (also used for parallel analysis)
    out_dir     : output directory for reports
    all_equity  : when True and universe is None, fetches all NSE EQ-series
                  equities (~1900) plus BSE-only stocks. Cached 24 h.
    on_batch    : callable(batch_results, done, total) fired after each batch
                  is ranked. Called from within the thread-pool (not the event
                  loop) — must be thread-safe.
    batch_size  : number of symbols per progressive batch (default 25)
    """
    from app.core.scanner.universe.nse_universe import get_full_universe

    t0 = time.time()

    # ---- Resolve universe ----
    if universe is None:
        universe = get_full_universe(
            include_midcap=True,
            include_smallcap=all_equity,
            all_equity=all_equity,
        )

    # ---- 1) Scanner agent: universe + parallel fetch + liquidity prefilter ----
    scanner = MarketScannerAgent(
        universe=universe,
        timeframes=timeframes,
        max_workers=workers,
    )
    logger.info("Scanning %d symbols across %s", len(scanner.universe), scanner.timeframes)
    if on_phase:
        try:
            on_phase("fetching_data", f"Fetching market data for {len(scanner.universe):,} stocks…")
        except Exception:
            pass
    universe_data = scanner.scan()
    logger.info("  -> %d symbols passed liquidity filter", len(universe_data))

    # Breakdown of why symbols were dropped at the prefilter stage, e.g.
    #   "820 no_data, 110 penny, 54 illiquid, 0 fetch_error"
    skipped = len(scanner.universe) - len(universe_data)
    if skipped > 0:
        breakdown = ", ".join(
            f"{cnt} {code}"
            for code, cnt in scanner.skip_reasons.most_common()
        )
        logger.info("  -> %d symbols skipped (%s)", skipped, breakdown)
        print(f"  -> {skipped} symbols skipped ({breakdown})")

    # ---- Scan-wide context: index (RS baseline) + sector momentum, computed once ----
    from app.core.scanner import data_fetcher
    from app.core.analysis import sector_engine

    try:
        index_df = data_fetcher.get_ohlcv(config.INDEX_SYMBOL, interval=config.SCAN_TIMEFRAME)
    except Exception as e:
        logger.warning("index fetch failed for %s: %s — RS will be neutral", config.INDEX_SYMBOL, e)
        index_df = None
    try:
        sector_momentum_map = sector_engine.compute_sector_momentum()
    except Exception as e:
        logger.warning("sector momentum computation failed: %s — sectors will be neutral", e)
        sector_momentum_map = {}
    fundamentals_map = fundamentals_map or {}

    # ---- 2+3) MTF Analysis + Risk: parallel within batches ----
    mtf_agent  = MTFAnalysisAgent()
    risk_agent = RiskManagementAgent()
    ranker     = SignalRankingAgent()

    symbols_to_analyze = list(universe_data.items())
    total_analysis = len(symbols_to_analyze)
    print(f"\n  Analyzing {total_analysis} symbols in batches of {batch_size}...\n")
    if on_phase:
        try:
            on_phase("analyzing", f"Analysing {total_analysis:,} stocks in batches…")
        except Exception:
            pass

    all_results: List[Dict] = []
    done_count = 0

    # Split into batches; each batch is analyzed in parallel then ranked atomically
    for batch_start in range(0, total_analysis, batch_size):
        batch = symbols_to_analyze[batch_start : batch_start + batch_size]
        enriched_batch: List[Dict] = []

        with ThreadPoolExecutor(max_workers=min(workers, len(batch))) as pool:
            future_to_sym = {
                pool.submit(
                    _analyze_one, sym, data, mtf_agent, risk_agent,
                    index_df, sector_momentum_map, fundamentals_map,
                ): sym
                for sym, data in batch
            }
            for future in as_completed(future_to_sym):
                result = future.result()
                if result is not None:
                    enriched_batch.append(result)
                done_count += 1

        # ---- 4) Rank & classify this batch ----
        ranked_batch = ranker.rank_and_classify(enriched_batch) if enriched_batch else []

        all_results.extend(ranked_batch)

        cats = Counter(r["classification"]["category"] for r in ranked_batch)
        batch_end = min(batch_start + batch_size, total_analysis)
        logger.info(
            "Batch %d–%d ranked: %s",
            batch_start + 1, batch_end,
            ", ".join(f"{v} {k}" for k, v in cats.items()),
        )
        print(
            f"  [Batch {batch_start + 1}–{batch_end}/{total_analysis}]  "
            + ", ".join(f"{v} {k}" for k, v in cats.items())
        )

        # Always fire the streaming callback — even for empty-signal batches —
        # so the progress counter advances and the UI doesn't appear frozen.
        if on_batch:
            try:
                on_batch(ranked_batch, done_count, total_analysis)
            except Exception:
                logger.exception("on_batch callback failed for batch starting at %d", batch_start)

    # ---- Summary ----
    cats = Counter(r["classification"]["category"] for r in all_results)
    parts = [
        f"{cats[c]} {c}"
        for c in ["INVESTMENT", "SWING", "POSITIONAL", "WATCH", "IGNORE"]
        if cats.get(c, 0) > 0
    ]
    print(f"\n  Ranked {len(all_results)} symbols: {',  '.join(parts)}\n")

    # ---- 5) Reporting (file output only; web platform uses DB instead) ----
    reporter = ReportGenerationAgent(out_dir=out_dir)
    scan_meta = {
        "scan_time":     datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        "universe_size": len(scanner.universe),
        "timeframes":    scanner.timeframes,
    }
    paths = reporter.render(all_results, detail_symbols=detail_symbols, scan_meta=scan_meta)

    dt = time.time() - t0
    logger.info(
        "Done in %.1fs. CSV: %s  JSON: %s  HTML: %s",
        dt, paths["csv"], paths["json"], paths.get("html", ""),
    )
    return all_results


def run_daily_scan(
    universe: Optional[List[str]] = None,
    out_dir: str = "./gate_output/daily",
    workers: int = 8,
    include_midcap: bool = True,
    include_smallcap: bool = False,
    include_fno_only: bool = False,
    all_equity: bool = False,
    on_batch: Optional[Callable[[list, int, int], None]] = None,
) -> List[Dict]:
    """
    Run the GATE scanner in daily-timeframe-only mode.

    Parameters
    ----------
    universe        : explicit list of symbols (overrides all include_* / all_equity flags)
    out_dir         : output directory for signals.csv / signals.json
    workers         : parallel fetch workers
    include_midcap  : include Nifty Midcap 150 in universe
    include_smallcap: include Nifty Smallcap 100 (adds noise; off by default)
    include_fno_only: use only F&O eligible stocks
    all_equity      : fetch every NSE EQ-series equity (~1900) + BSE-only stocks; cached 24 h
    on_batch        : streaming callback — see run_scan() docstring
    """
    from app.core.scanner.universe.nse_universe import get_full_universe

    if universe is None:
        universe = get_full_universe(
            include_midcap=include_midcap,
            include_smallcap=include_smallcap or all_equity,
            include_fno_only=include_fno_only,
            all_equity=all_equity,
        )

    logger.info(
        "Daily scan: %d symbols, timeframes=%s, output=%s",
        len(universe), config.SCAN_TIMEFRAMES, out_dir,
    )

    return run_scan(
        universe=universe,
        timeframes=config.SCAN_TIMEFRAMES,   # ["4h", "1d", "1wk"] — 4h for SL, 1d entry, 1wk HTF
        workers=workers,
        out_dir=out_dir,
        on_batch=on_batch,
    )
