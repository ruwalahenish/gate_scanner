"""
daily_scanner.py
=================
Daily-timeframe-only entry point for the GATE Scanner.

Designed for end-of-day use after NSE market close (after 3:30 PM IST).
Uses the full NSE/BSE/F&O universe by default (~700 symbols with midcap).

Run manually:
    python -m gate_scanner.daily_scanner

Or via the scheduler:
    python -m gate_scanner.scheduler
"""

from __future__ import annotations

import argparse
import logging
from typing import List, Optional

from .main import run_scan
from .universe.nse_universe import get_full_universe

logger = logging.getLogger("gate_scanner.daily")


def run_daily_scan(
    universe: Optional[List[str]] = None,
    out_dir: str = "./gate_output/daily",
    workers: int = 8,
    include_midcap: bool = True,
    include_smallcap: bool = False,
    include_fno_only: bool = False,
    all_equity: bool = False,
) -> list:
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
    all_equity      : fetch every NSE EQ-series equity (~1900) + BSE-only stocks;
                      cached 24 h in .gate_cache/

    Returns
    -------
    List of ranked result dicts (same as run_scan output)
    """
    if universe is None:
        universe = get_full_universe(
            include_midcap=include_midcap,
            include_smallcap=include_smallcap or all_equity,
            include_fno_only=include_fno_only,
            all_equity=all_equity,
        )

    logger.info(
        "Daily scan: %d symbols, timeframe=1d, output=%s",
        len(universe), out_dir,
    )

    return run_scan(
        universe=universe,
        timeframes=["1d"],
        workers=workers,
        out_dir=out_dir,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _cli():
    parser = argparse.ArgumentParser(
        description="GATE Daily Scanner — end-of-day NSE opportunity scan"
    )
    parser.add_argument(
        "--universe", nargs="+", default=None,
        help="Explicit symbol list. Default = full NSE/F&O universe.",
    )
    parser.add_argument("--out", default="./gate_output/daily")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--fno-only", action="store_true",
        help="Restrict universe to F&O eligible stocks only.",
    )
    parser.add_argument(
        "--include-smallcap", action="store_true",
        help="Add Nifty Smallcap 100 to universe.",
    )
    parser.add_argument(
        "--all-stocks", action="store_true",
        help=(
            "Scan every equity listed on NSE (EQ series, ~1900 symbols) and BSE. "
            "Fetches live symbol lists cached for 24 h. "
            "Liquidity filter (price ≥ ₹20, avg vol ≥ 1L) still applies."
        ),
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    run_daily_scan(
        universe=args.universe,
        out_dir=args.out,
        workers=args.workers,
        include_fno_only=args.fno_only,
        include_smallcap=args.include_smallcap,
        all_equity=args.all_stocks,
    )


if __name__ == "__main__":
    _cli()
