"""
backtester/engine.py
=====================
Walk-forward GATE backtest engine.

Design
------
* No look-ahead bias: at each bar we only see data up to (and including) that bar.
* Daily-timeframe only — consistent with the GATE Strategy's preferred entry TF.
* Entry: next bar open after a signal fires (simulate realistic fill).
* Exit: checked against the bar's high/low using the trailing-SL ladder.
* Walk-forward windows: optional. Defaults to a single in-sample run.

Usage
-----
from app.core.backtester import BacktestEngine

engine = BacktestEngine(
    universe=["RELIANCE", "TCS", "INFY"],
    start_date="2022-01-01",
    end_date="2024-12-31",
)
portfolio = engine.run()
"""

from __future__ import annotations

import concurrent.futures as cf
import logging
from typing import Dict, List, Optional

import pandas as pd

from app.core import config
from app.core.scanner.data_fetcher import get_bulk_history
from app.agents.mtf_agent import MTFAnalysisAgent
from app.agents.risk_agent import RiskManagementAgent
from .portfolio import Portfolio
from .trade import Trade

logger = logging.getLogger(__name__)

# Bars fed to the GATE pipeline per symbol per scan.
# EMA200 needs 200 bars; GATE lookbacks need 100 bars. 300 is ample and avoids
# passing a growing multi-year slice to the engines on every bar.
_SLICE_BARS = 300


class BacktestEngine:
    def __init__(
        self,
        universe: List[str],
        start_date: str = config.BACKTEST_START_DATE,
        end_date: Optional[str] = config.BACKTEST_END_DATE,
        timeframe: str = config.BACKTEST_TIMEFRAME,
        initial_capital: float = config.BACKTEST_CAPITAL,
        position_size_pct: float = config.BACKTEST_POSITION_PCT,
        max_positions: int = config.BACKTEST_MAX_POSITIONS,
        workers: int = 4,
        warm_up_bars: int = 200,
        scan_interval: int = 5,
    ):
        self.universe        = universe
        self.start_date      = pd.Timestamp(start_date)
        self.end_date        = pd.Timestamp(end_date) if end_date else pd.Timestamp.today()
        self.timeframe       = timeframe
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.max_positions   = max_positions
        self.workers         = workers
        self.warm_up_bars    = warm_up_bars
        self.scan_interval   = scan_interval  # run signal scan every N bars (GATE setups persist for weeks)

        self._mtf_agent  = MTFAnalysisAgent()
        self._risk_agent = RiskManagementAgent()
        self.history: Dict[str, pd.DataFrame] = {}   # populated by run(); used for trade charts

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> Portfolio:
        """Execute the full walk-forward simulation. Returns a completed Portfolio."""
        logger.info(
            "BacktestEngine: loading history for %d symbols (%s → %s)",
            len(self.universe), self.start_date.date(), self.end_date.date(),
        )

        # Fetch full history (fetch from before start_date to allow warm-up)
        fetch_start = (self.start_date - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
        history: Dict[str, pd.DataFrame] = get_bulk_history(
            self.universe,
            interval=self.timeframe,
            start=fetch_start,
            end=self.end_date.strftime("%Y-%m-%d"),
            workers=self.workers,
        )
        self.history = history   # stored for trade chart generation after run()
        logger.info("  -> history loaded for %d symbols", len(history))

        # Build the sorted list of trading days in the backtest window
        all_dates: pd.DatetimeIndex = pd.DatetimeIndex(sorted({
            idx for df in history.values()
            for idx in df.index
            if self.start_date <= idx <= self.end_date
        }))

        total_dates = len(all_dates)
        logger.info(
            "  -> %d trading days in simulation window  (scan every %d bars, %d-bar window)",
            total_dates, self.scan_interval, _SLICE_BARS,
        )

        portfolio = Portfolio(
            initial_capital=self.initial_capital,
            position_size_pct=self.position_size_pct,
            max_open_positions=self.max_positions,
        )

        # Signals pending entry on next bar: { symbol: signal_dict }
        pending_entries: Dict[str, dict] = {}
        last_print_month: tuple = ()

        with cf.ThreadPoolExecutor(max_workers=self.workers) as executor:
            for i, date in enumerate(all_dates):
                # ---- Progress output (once per month) ----
                m = (date.year, date.month)
                if m != last_print_month:
                    pct = i / total_dates * 100
                    print(
                        f"  [Backtest {pct:5.1f}%] {date.strftime('%Y-%m')}  "
                        f"open={len(portfolio._open)}  "
                        f"closed={len(portfolio.closed_trades)}"
                    )
                    last_print_month = m

                price_map = {sym: float(history[sym].loc[date, "Close"])
                            for sym in history if date in history[sym].index}

                # ---- 1) Process exits on open positions ----
                for sym in list(portfolio._open.keys()):
                    if sym not in history or date not in history[sym].index:
                        continue
                    bar = history[sym].loc[date]
                    trade = portfolio._open[sym]
                    exit_price, reason = self._check_exit(trade, bar)
                    if exit_price is not None:
                        portfolio.close_position(sym, date, exit_price, reason)
                    else:
                        # Update trailing SL if targets hit (but no exit yet)
                        self._update_trail(portfolio, trade, bar, date)

                # ---- 2) Enter positions from prior bar's signals ----
                for sym, sig in list(pending_entries.items()):
                    if sym in portfolio._open:
                        del pending_entries[sym]
                        continue
                    if sym not in history or date not in history[sym].index:
                        continue
                    entry_price = float(history[sym].loc[date, "Open"])
                    trade = Trade(
                        symbol=sym,
                        entry_date=date,
                        entry_price=entry_price,
                        sl_price=sig["stop_loss"],
                        t1=sig["T1"],
                        t2=sig["T2"],
                        t3=sig["T3"],
                        tf=sig.get("signal_timeframe", self.timeframe),
                        category=sig.get("category", ""),
                    )
                    portfolio.open_position(trade)
                    del pending_entries[sym]

                # ---- 3) Scan for new signals (skip warmup; run every scan_interval bars) ----
                active = i - self.warm_up_bars
                if active >= 0 and active % self.scan_interval == 0:
                    new_signals = self._scan_bar(history, date, portfolio, executor)
                    for sym, sig in new_signals.items():
                        if sym not in portfolio._open and sym not in pending_entries:
                            pending_entries[sym] = sig

                # ---- 4) Mark-to-market ----
                portfolio.mark_to_market(date, price_map)

        # ---- Close any remaining open positions at last bar ----
        last_date = all_dates[-1] if len(all_dates) else self.end_date
        last_prices = {sym: float(history[sym]["Close"].iloc[-1])
                      for sym in history if not history[sym].empty}
        portfolio.liquidate_all(last_date, last_prices)

        logger.info(
            "Backtest complete: %d trades, final equity ₹%s",
            len(portfolio.closed_trades),
            f"{portfolio.equity:,.0f}",
        )
        return portfolio

    # ------------------------------------------------------------------
    # Per-bar signal scan
    # ------------------------------------------------------------------

    def _scan_bar(
        self,
        history: Dict[str, pd.DataFrame],
        date: pd.Timestamp,
        portfolio: Portfolio,
        executor: cf.ThreadPoolExecutor,
    ) -> Dict[str, dict]:
        """
        Run the GATE pipeline on a slice of history up to `date` for every symbol
        not already in the portfolio. Returns {symbol: signal_dict}.
        Per-symbol analysis is independent, so we parallelise across self.workers.
        """
        open_set = set(portfolio._open.keys())

        def _work(sym: str):
            if sym in open_set:
                return sym, None
            full_df = history[sym]
            # searchsorted(side='right') gives the exclusive upper bound for date,
            # so iloc[...: end_pos] includes date but nothing beyond it (no look-ahead).
            end_pos = full_df.index.searchsorted(date, side="right")
            df_slice = full_df.iloc[max(0, end_pos - _SLICE_BARS): end_pos]
            if len(df_slice) < 50:
                return sym, None
            try:
                mtf_data = {self.timeframe: df_slice}
                mtf_result = self._mtf_agent.analyze(mtf_data, symbol=sym)
                signal = self._risk_agent.build_signal(
                    sym,
                    mtf_data,
                    mtf_result["per_tf"],
                    mtf_result["summary"],
                )
                if signal and signal.get("entry"):
                    return sym, signal
            except Exception as e:
                logger.debug("scan_bar error for %s @ %s: %s", sym, date.date(), e)
            return sym, None

        signals: Dict[str, dict] = {}
        for sym, sig in executor.map(_work, history.keys()):
            if sig is not None:
                signals[sym] = sig
        return signals

    # ------------------------------------------------------------------
    # Exit / trail logic
    # ------------------------------------------------------------------

    @staticmethod
    def _check_exit(trade: Trade, bar: pd.Series):
        """
        Evaluate whether this bar triggers an exit.
        Returns (exit_price, reason) or (None, "").

        Exit priority:
          1. SL hit (low <= trailing_sl)  → exit at trailing_sl
          2. T3 hit (high >= t3)          → full exit at T3
          3. T2 hit (high >= t2)          → ratchet trail to T1 (no exit yet)
          4. T1 hit (high >= t1)          → ratchet trail to entry (no exit yet)
        """
        lo  = float(bar["Low"])
        hi  = float(bar["High"])

        if lo <= trade.trailing_sl:
            return trade.trailing_sl, "SL"
        if hi >= trade.t3:
            return trade.t3, "T3"
        return None, ""

    @staticmethod
    def _update_trail(
        portfolio: Portfolio,
        trade: Trade,
        bar: pd.Series,
        date: pd.Timestamp,
    ) -> None:
        """Ratchet trailing SL when T1 or T2 is touched."""
        hi = float(bar["High"])
        if hi >= trade.t2:
            portfolio.update_trailing_sl(trade.symbol, trade.t1, date)
        elif hi >= trade.t1:
            portfolio.update_trailing_sl(trade.symbol, trade.entry_price, date)
