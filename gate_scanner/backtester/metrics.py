"""
backtester/metrics.py
======================
Compute performance statistics from a completed Portfolio.

All return-rates are expressed as decimals (0.15 = 15%).
"""

from __future__ import annotations

import math
from typing import Dict

import pandas as pd

from .portfolio import Portfolio


def compute_metrics(portfolio: Portfolio) -> Dict:
    trades = portfolio.closed_trades
    eq = portfolio.equity_curve

    n = len(trades)
    if n == 0:
        return _empty_metrics()

    # ------------------------------------------------------------------
    # Trade-level stats
    # ------------------------------------------------------------------
    winners = [t for t in trades if t.is_winner]
    losers  = [t for t in trades if not t.is_winner]

    win_rate      = len(winners) / n
    gross_profit  = sum(t.pnl_abs for t in winners)
    gross_loss    = abs(sum(t.pnl_abs for t in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win_pct   = sum(t.pnl_pct for t in winners) / len(winners) if winners else 0.0
    avg_loss_pct  = sum(t.pnl_pct for t in losers)  / len(losers)  if losers  else 0.0
    avg_rr        = sum(t.rr_achieved for t in trades) / n

    best_trade    = max(trades, key=lambda t: t.pnl_pct)
    worst_trade   = min(trades, key=lambda t: t.pnl_pct)
    avg_holding   = sum(t.holding_days for t in trades) / n

    # ------------------------------------------------------------------
    # Portfolio-level stats
    # ------------------------------------------------------------------
    if not eq.empty and len(eq) > 1:
        start_eq   = eq.iloc[0]
        end_eq     = eq.iloc[-1]
        total_days = max(1, (eq.index[-1] - eq.index[0]).days)
        total_return = (end_eq - start_eq) / start_eq

        cagr = (end_eq / start_eq) ** (365.0 / total_days) - 1

        daily_ret = eq.pct_change().dropna()
        if daily_ret.std() > 0:
            sharpe = daily_ret.mean() / daily_ret.std() * math.sqrt(252)
        else:
            sharpe = 0.0

        max_dd = portfolio.max_drawdown
        calmar = cagr / abs(max_dd) if max_dd != 0 else float("inf")
    else:
        total_return = cagr = sharpe = calmar = 0.0
        max_dd = portfolio.max_drawdown

    # ------------------------------------------------------------------
    # Monthly / yearly breakdown
    # ------------------------------------------------------------------
    monthly_returns = _period_returns(eq, "ME")
    yearly_returns  = _period_returns(eq, "YE")

    return {
        "total_trades":    n,
        "win_rate":        win_rate,
        "profit_factor":   profit_factor,
        "avg_rr_achieved": avg_rr,
        "avg_win_pct":     avg_win_pct,
        "avg_loss_pct":    avg_loss_pct,
        "best_trade_pct":  best_trade.pnl_pct,
        "best_trade_sym":  best_trade.symbol,
        "worst_trade_pct": worst_trade.pnl_pct,
        "worst_trade_sym": worst_trade.symbol,
        "avg_holding_days":avg_holding,
        "total_return":    total_return,
        "cagr":            cagr,
        "sharpe_ratio":    sharpe,
        "calmar_ratio":    calmar,
        "max_drawdown":    max_dd,
        "monthly_returns": monthly_returns,
        "yearly_returns":  yearly_returns,
    }


def _period_returns(equity: pd.Series, freq: str) -> pd.Series:
    """Resample equity curve to period-end values and compute period returns."""
    if equity.empty:
        return pd.Series(dtype=float)
    resampled = equity.resample(freq).last().dropna()
    return resampled.pct_change().dropna()


def _empty_metrics() -> Dict:
    return {
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_rr_achieved": 0.0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "best_trade_pct": 0.0,
        "best_trade_sym": "",
        "worst_trade_pct": 0.0,
        "worst_trade_sym": "",
        "avg_holding_days": 0.0,
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe_ratio": 0.0,
        "calmar_ratio": 0.0,
        "max_drawdown": 0.0,
        "monthly_returns": pd.Series(dtype=float),
        "yearly_returns": pd.Series(dtype=float),
    }
