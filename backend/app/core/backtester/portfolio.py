"""
backtester/portfolio.py
========================
Tracks capital, open positions, equity curve, and drawdown across a backtest run.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .trade import Trade


class Portfolio:
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        position_size_pct: float = 0.05,
        max_open_positions: int = 10,
    ):
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.max_open_positions = max_open_positions

        self._cash: float = initial_capital
        self._open: Dict[str, Trade] = {}           # symbol -> Trade
        self._closed: List[Trade] = []
        self._equity_history: List[Tuple[pd.Timestamp, float]] = []  # (date, equity)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @property
    def open_count(self) -> int:
        return len(self._open)

    @property
    def invested_value(self) -> float:
        return sum(t.entry_price * t.quantity for t in self._open.values())

    @property
    def equity(self) -> float:
        return self._cash + self.invested_value

    # ------------------------------------------------------------------
    # Position management
    # ------------------------------------------------------------------

    def open_position(self, trade: Trade) -> bool:
        """
        Allocate capital and record an open position.
        Returns False (and does nothing) if:
          - symbol already in portfolio
          - max positions reached
          - insufficient cash
        """
        if trade.symbol in self._open:
            return False
        if self.open_count >= self.max_open_positions:
            return False

        alloc = self.equity * self.position_size_pct
        qty = math.floor(alloc / trade.entry_price)
        if qty < 1:
            return False

        cost = qty * trade.entry_price
        if cost > self._cash:
            return False

        trade.quantity = qty
        trade.trailing_sl = trade.sl_price
        self._cash -= cost
        self._open[trade.symbol] = trade
        return True

    def close_position(
        self,
        symbol: str,
        exit_date: pd.Timestamp,
        exit_price: float,
        reason: str,
    ) -> Optional[Trade]:
        """Close an open position and return the completed Trade, or None."""
        trade = self._open.pop(symbol, None)
        if trade is None:
            return None
        trade.exit_date = exit_date
        trade.exit_price = exit_price
        trade.exit_reason = reason
        self._cash += exit_price * trade.quantity
        self._closed.append(trade)
        return trade

    def update_trailing_sl(
        self,
        symbol: str,
        new_sl: float,
        date: "pd.Timestamp | None" = None,
    ) -> None:
        """Ratchet up the trailing stop (never lower it). Records date-stamped history."""
        trade = self._open.get(symbol)
        if trade and new_sl > trade.trailing_sl:
            trade.trailing_sl = new_sl
            if date is not None:
                trade.trailing_sl_history.append((date, new_sl))

    # ------------------------------------------------------------------
    # Mark-to-market (called once per bar to record equity curve)
    # ------------------------------------------------------------------

    def mark_to_market(
        self,
        date: pd.Timestamp,
        price_map: Dict[str, float],
    ) -> None:
        """
        Revalue open positions at current market prices and append to equity history.
        `price_map` = {symbol: close_price} for the current bar.
        """
        mtm = self._cash
        for sym, trade in self._open.items():
            price = price_map.get(sym, trade.entry_price)
            mtm += price * trade.quantity
        self._equity_history.append((date, mtm))

    # ------------------------------------------------------------------
    # Close all open positions (end of backtest)
    # ------------------------------------------------------------------

    def liquidate_all(self, date: pd.Timestamp, price_map: Dict[str, float]) -> None:
        for sym in list(self._open.keys()):
            price = price_map.get(sym, self._open[sym].entry_price)
            self.close_position(sym, date, price, "EOD")

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    @property
    def closed_trades(self) -> List[Trade]:
        return list(self._closed)

    @property
    def equity_curve(self) -> pd.Series:
        if not self._equity_history:
            return pd.Series(dtype=float)
        dates, values = zip(*self._equity_history)
        return pd.Series(values, index=pd.DatetimeIndex(dates), name="equity")

    @property
    def drawdown_series(self) -> pd.Series:
        eq = self.equity_curve
        if eq.empty:
            return pd.Series(dtype=float)
        peak = eq.cummax()
        return ((eq - peak) / peak).rename("drawdown")

    @property
    def max_drawdown(self) -> float:
        dd = self.drawdown_series
        return float(dd.min()) if not dd.empty else 0.0
