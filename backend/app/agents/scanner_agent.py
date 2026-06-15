"""
agents/scanner_agent.py
========================
Responsibilities:
  * Maintain the stock universe (default NIFTY 50 + Next 50 sample)
  * Fetch multi-timeframe data per symbol
  * Apply liquidity/price prefilters
"""

from __future__ import annotations

import concurrent.futures as cf
from collections import Counter
from typing import Dict, List, Optional

import pandas as pd

from app.agents.base import BaseAgent
from app.core import config
from app.core.scanner import data_fetcher as data_fetcher


class MarketScannerAgent(BaseAgent):
    def __init__(
        self,
        universe: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        max_workers: int = 8,
        min_price: float = config.MIN_PRICE,
        min_volume: int = config.MIN_AVG_VOLUME,
    ):
        super().__init__()
        self.universe   = universe or config.DEFAULT_UNIVERSE
        # GATE Strategy — Daily TF platform.
        # config.SCAN_TIMEFRAMES = ["4h", "1d", "1wk"]:
        #   4h  — SL source   (SL_TIMEFRAME_MAP["1d"] = "4h")
        #   1d  — entry signal (SCAN_TIMEFRAME)
        #   1wk — HTF confirmation
        self.timeframes = timeframes or config.SCAN_TIMEFRAMES
        self.max_workers = max_workers
        self.min_price  = min_price
        self.min_volume = min_volume
        # Populated by scan(): {reason_code: count} for symbols that did NOT
        # pass the liquidity/price prefilter. Reason codes:
        #   "no_data"     — yfinance returned empty / < 20 daily bars
        #   "penny"       — last close < min_price
        #   "illiquid"    — 20-bar avg volume < min_volume
        #   "fetch_error" — exception while fetching/parsing
        self.skip_reasons: Counter = Counter()

    # -------------------------------------------------------------------------
    # Liquidity / price filter (run on daily TF after fetch)
    # -------------------------------------------------------------------------
    def passes_liquidity(self, df_daily: pd.DataFrame) -> bool:
        if df_daily is None or df_daily.empty or len(df_daily) < 20:
            return False
        last_close = df_daily["Close"].iloc[-1]
        avg_volume = df_daily["Volume"].iloc[-20:].mean()
        return (last_close >= self.min_price) and (avg_volume >= self.min_volume)

    # -------------------------------------------------------------------------
    # Single symbol fetch
    # -------------------------------------------------------------------------
    def fetch_symbol(self, symbol: str) -> Dict[str, pd.DataFrame]:
        return data_fetcher.get_multi_timeframe(symbol, intervals=self.timeframes)

    # -------------------------------------------------------------------------
    # Parallel fetch over universe
    # -------------------------------------------------------------------------
    def scan(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Returns { symbol: { tf: DataFrame } } after liquidity filter.

        Side effect: populates self.skip_reasons (Counter of reason_code -> count)
        for every symbol that did not pass the prefilter, so callers can report a
        breakdown of *why* the scanned universe shrank.
        """
        out: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.skip_reasons = Counter()
        total = len(self.universe)

        print(f"\n  Fetching data for {total} symbols...\n")

        def _work(sym):
            try:
                mtf = self.fetch_symbol(sym)
                daily = mtf.get("1d")
                if daily is None or daily.empty or len(daily) < 20:
                    return sym, None, "no_data", "insufficient data"
                last_close = float(daily["Close"].iloc[-1])
                avg_vol = float(daily["Volume"].iloc[-20:].mean())
                if last_close < self.min_price:
                    return sym, None, "penny", f"price ₹{last_close:.0f} < min ₹{self.min_price:.0f}"
                if avg_vol < self.min_volume:
                    return sym, None, "illiquid", f"avg vol {avg_vol/1e5:.1f}L < min {self.min_volume/1e5:.0f}L"
                return sym, mtf, None, f"close=₹{last_close:.2f}  avg_vol={avg_vol/1e5:.1f}L"
            except Exception as e:
                self._log.warning("scan failed for %s: %s", sym, e)
                return sym, None, "fetch_error", f"fetch error: {e}"

        with cf.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(_work, sym): sym for sym in self.universe}
            for idx, fut in enumerate(cf.as_completed(futures), 1):
                sym, mtf, reason_code, detail = fut.result()
                status = "PASS" if mtf is not None else "SKIP"
                print(f"  [Fetch {idx:3d}/{total}] {sym:<22}  {status:<4}  {detail}")
                if mtf is not None:
                    out[sym] = mtf
                else:
                    self.skip_reasons[reason_code] += 1
        return out
