"""
backtester/trade.py
====================
Trade dataclass: records every entry/exit event for one position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Trade:
    symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    sl_price: float
    t1: float
    t2: float
    t3: float
    quantity: int = 1
    tf: str = "1d"                       # timeframe that generated the signal
    category: str = ""                   # INVESTMENT / SWING / POSITIONAL
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""                # "SL" | "T1" | "T2" | "T3" | "TRAIL" | "EOD"
    # Trailing SL state
    trailing_sl: float = field(default=0.0, repr=False)
    # History of SL ratchets: [(date, new_sl_value), ...]  — used for trade charts
    trailing_sl_history: list = field(default_factory=list, repr=False)

    def __post_init__(self):
        if self.trailing_sl == 0.0:
            self.trailing_sl = self.sl_price

    # ------------------------------------------------------------------
    # Computed properties (only valid after exit)
    # ------------------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self.exit_price is None

    @property
    def pnl_pct(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) / self.entry_price

    @property
    def pnl_abs(self) -> float:
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) * self.quantity

    @property
    def holding_days(self) -> int:
        if self.exit_date is None:
            return 0
        return max(1, (self.exit_date - self.entry_date).days)

    @property
    def is_winner(self) -> bool:
        return self.pnl_pct > 0

    @property
    def rr_achieved(self) -> float:
        risk = self.entry_price - self.sl_price
        if risk <= 0:
            return 0.0
        return (self.exit_price - self.entry_price) / risk if self.exit_price else 0.0

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "symbol":       self.symbol,
            "entry_date":   str(self.entry_date.date()) if self.entry_date else "",
            "exit_date":    str(self.exit_date.date()) if self.exit_date else "",
            "entry_price":  round(self.entry_price, 2),
            "exit_price":   round(self.exit_price, 2) if self.exit_price else "",
            "sl_price":     round(self.sl_price, 2),
            "t1":           round(self.t1, 2),
            "t2":           round(self.t2, 2),
            "t3":           round(self.t3, 2),
            "quantity":     self.quantity,
            "pnl_pct":      round(self.pnl_pct * 100, 2),
            "pnl_abs":      round(self.pnl_abs, 2),
            "holding_days": self.holding_days,
            "exit_reason":  self.exit_reason,
            "category":     self.category,
            "tf":           self.tf,
        }
