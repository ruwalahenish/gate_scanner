"""
backtester/report.py
=====================
Generate HTML and CSV reports from a completed backtest.

HTML report:
  - Interactive Plotly equity curve + drawdown chart
  - Summary metrics table
  - Monthly returns heatmap (color-coded green / red)
  - Yearly returns table
  - Top-10 and Bottom-10 trades (with links to individual candlestick chart files)

CSV files:
  - trades.csv      — full trade log
  - monthly_returns.csv
  - equity_curve.csv

Per-trade charts:
  - gate_output/backtest/charts/{SYMBOL}_{entry_date}.html
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from .portfolio import Portfolio
from .metrics import compute_metrics  # noqa: F401 (re-exported for callers)


class BacktestReport:
    def __init__(
        self,
        portfolio: Portfolio,
        metrics: Dict,
        out_dir: str = "./gate_output/backtest",
        history: Optional[Dict[str, pd.DataFrame]] = None,
    ):
        self.portfolio = portfolio
        self.metrics   = metrics
        self.out_dir   = Path(out_dir)
        self.history   = history or {}   # { symbol: OHLCV DataFrame } for trade charts
        self.out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def render_csv(self) -> Dict[str, str]:
        """Write all CSV files. Returns dict of {name: path}."""
        paths = {}

        # trades.csv
        trades_path = self.out_dir / "trades.csv"
        trades = self.portfolio.closed_trades
        if trades:
            fieldnames = list(trades[0].to_dict().keys())
            with open(trades_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(t.to_dict() for t in trades)
        paths["trades"] = str(trades_path)

        # monthly_returns.csv
        monthly = self.metrics.get("monthly_returns", pd.Series(dtype=float))
        if not monthly.empty:
            mr_path = self.out_dir / "monthly_returns.csv"
            monthly.rename("return_pct").multiply(100).round(2).to_csv(mr_path, header=True)
            paths["monthly_returns"] = str(mr_path)

        # equity_curve.csv
        eq = self.portfolio.equity_curve
        if not eq.empty:
            eq_path = self.out_dir / "equity_curve.csv"
            dd = self.portfolio.drawdown_series
            pd.DataFrame({"equity": eq, "drawdown_pct": (dd * 100).round(2)}).to_csv(eq_path)
            paths["equity_curve"] = str(eq_path)

        return paths

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------

    def render_html(self) -> str:
        """Write self-contained HTML report. Returns file path."""
        html_path = self.out_dir / "backtest_report.html"
        html = _build_html(self.portfolio, self.metrics, self.history, self.out_dir)
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        return str(html_path)

    # ------------------------------------------------------------------
    # Combined render
    # ------------------------------------------------------------------

    def render(self) -> Dict[str, str]:
        """Render all outputs. Returns all paths."""
        paths = self.render_csv()
        paths["html"] = self.render_html()
        return paths


# ---------------------------------------------------------------------------
# HTML builder (pure Python string manipulation — no external libs)
# ---------------------------------------------------------------------------

def _build_html(
    portfolio: Portfolio,
    m: Dict,
    history: Optional[Dict[str, pd.DataFrame]] = None,
    out_dir: Optional[Path] = None,
) -> str:
    from .. import charting

    trades = portfolio.closed_trades

    summary_html = _summary_table(m)
    monthly_html = _monthly_heatmap(m.get("monthly_returns", pd.Series(dtype=float)))
    yearly_html  = _yearly_table(m.get("yearly_returns", pd.Series(dtype=float)))
    top10_html   = _top_n_trades(trades, n=10, best=True,  history=history, out_dir=out_dir)
    bot10_html   = _top_n_trades(trades, n=10, best=False, history=history, out_dir=out_dir)
    equity_html   = charting.build_equity_chart(portfolio.equity_curve, portfolio.drawdown_series)
    plotly_js_tag = charting.get_plotly_js_tag()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GATE Backtest Report</title>
{plotly_js_tag}
<style>
  body {{ font-family: Arial, sans-serif; margin: 24px; background: #f5f5f5; color: #222; }}
  h1 {{ color: #1a3c5e; }}
  h2 {{ color: #1a3c5e; margin-top: 32px; border-bottom: 2px solid #1a3c5e; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; background: #fff; }}
  th {{ background: #1a3c5e; color: #fff; padding: 8px 12px; text-align: left; font-size: 13px; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #ddd; font-size: 13px; }}
  tr:hover td {{ background: #f0f4fa; }}
  .pos {{ color: #1a7a43; font-weight: bold; }}
  .neg {{ color: #b71c1c; font-weight: bold; }}
  .hm-pos {{ background: #c8e6c9; }}
  .hm-neg {{ background: #ffcdd2; }}
  .hm-zero {{ background: #eeeeee; }}
  pre {{ background: #1a1a2e; color: #a0d8ef; padding: 16px; border-radius: 4px; overflow-x: auto; font-size: 12px; }}
</style>
</head>
<body>
<h1>GATE Strategy — Backtest Report</h1>

<h2>Summary Metrics</h2>
{summary_html}

<h2>Equity Curve</h2>
{equity_html}

<h2>Monthly Returns</h2>
{monthly_html}

<h2>Yearly Returns</h2>
{yearly_html}

<h2>Top 10 Trades</h2>
{top10_html}

<h2>Bottom 10 Trades</h2>
{bot10_html}

</body>
</html>"""


def _pct(v: float, decimals: int = 1) -> str:
    cls = "pos" if v >= 0 else "neg"
    return f'<span class="{cls}">{v:+.{decimals}f}%</span>'


def _summary_table(m: Dict) -> str:
    rows = [
        ("Total Trades",        str(m["total_trades"])),
        ("Win Rate",            f'{m["win_rate"]*100:.1f}%'),
        ("Profit Factor",       f'{m["profit_factor"]:.2f}'),
        ("Avg R:R Achieved",    f'{m["avg_rr_achieved"]:.2f}'),
        ("Total Return",        _pct(m["total_return"] * 100)),
        ("CAGR",                _pct(m["cagr"] * 100)),
        ("Sharpe Ratio",        f'{m["sharpe_ratio"]:.2f}'),
        ("Calmar Ratio",        f'{m["calmar_ratio"]:.2f}'),
        ("Max Drawdown",        _pct(m["max_drawdown"] * 100)),
        ("Avg Holding Days",    f'{m["avg_holding_days"]:.1f}'),
        ("Best Trade",          f'{m["best_trade_sym"]} ({_pct(m["best_trade_pct"] * 100)})'),
        ("Worst Trade",         f'{m["worst_trade_sym"]} ({_pct(m["worst_trade_pct"] * 100)})'),
        ("Avg Win",             _pct(m["avg_win_pct"] * 100)),
        ("Avg Loss",            _pct(m["avg_loss_pct"] * 100)),
    ]
    body = "".join(
        f"<tr><td><strong>{label}</strong></td><td>{value}</td></tr>"
        for label, value in rows
    )
    return f"<table><tr><th>Metric</th><th>Value</th></tr>{body}</table>"


def _monthly_heatmap(monthly: pd.Series) -> str:
    if monthly.empty:
        return "<p>No data</p>"

    # Build year x month pivot
    df = monthly.rename("ret").to_frame()
    df.index = pd.to_datetime(df.index)
    df["year"]  = df.index.year
    df["month"] = df.index.month
    pivot = df.pivot(index="year", columns="month", values="ret")

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    header = "".join(f"<th>{m}</th>" for m in months)
    rows = f"<tr><th>Year</th>{header}<th>Annual</th></tr>"

    for year in sorted(pivot.index):
        annual = (1 + pivot.loc[year].fillna(0)).prod() - 1
        cells = ""
        for mo in range(1, 13):
            val = pivot.loc[year].get(mo)
            if pd.isna(val) or val is None:
                cells += "<td>—</td>"
            else:
                cls = "hm-pos" if val >= 0 else "hm-neg"
                cells += f'<td class="{cls}">{val*100:+.1f}%</td>'
        ann_cls = "hm-pos" if annual >= 0 else "hm-neg"
        rows += f'<tr><td><strong>{year}</strong></td>{cells}<td class="{ann_cls}"><strong>{annual*100:+.1f}%</strong></td></tr>'

    return f"<table>{rows}</table>"


def _yearly_table(yearly: pd.Series) -> str:
    if yearly.empty:
        return "<p>No data</p>"
    rows = "<tr><th>Year</th><th>Return</th></tr>"
    for dt, val in yearly.items():
        year = pd.Timestamp(dt).year
        rows += f"<tr><td>{year}</td><td>{_pct(val * 100)}</td></tr>"
    return f"<table>{rows}</table>"


def _top_n_trades(
    trades,
    n: int = 10,
    best: bool = True,
    history: Optional[Dict[str, pd.DataFrame]] = None,
    out_dir: Optional[Path] = None,
) -> str:
    if not trades:
        return "<p>No trades</p>"
    from .. import charting

    sorted_trades = sorted(trades, key=lambda t: t.pnl_pct, reverse=best)[:n]
    header = (
        "<tr><th>Symbol</th><th>Entry</th><th>Exit</th>"
        "<th>P&amp;L %</th><th>P&amp;L ₹</th><th>Holding</th><th>Reason</th></tr>"
    )
    rows = header
    for t in sorted_trades:
        cls = "pos" if t.is_winner else "neg"

        # Generate trade chart and make symbol a clickable link
        symbol_cell = t.symbol
        if history and out_dir:
            ohlcv_df = history.get(t.symbol)
            if ohlcv_df is not None and not ohlcv_df.empty:
                safe_date  = str(t.entry_date.date()) if t.entry_date else "unknown"
                chart_file = f"{t.symbol}_{safe_date}.html"
                chart_path = str(out_dir / "charts" / chart_file)
                saved = charting.build_trade_chart(t.symbol, ohlcv_df, t, chart_path)
                if saved:
                    symbol_cell = f'<a href="charts/{chart_file}" target="_blank">{t.symbol}</a>'

        rows += (
            f"<tr>"
            f"<td>{symbol_cell}</td>"
            f"<td>{t.entry_date.date() if t.entry_date else ''}</td>"
            f"<td>{t.exit_date.date() if t.exit_date else ''}</td>"
            f'<td class="{cls}">{t.pnl_pct*100:+.1f}%</td>'
            f"<td>₹{t.pnl_abs:,.0f}</td>"
            f"<td>{t.holding_days}d</td>"
            f"<td>{t.exit_reason}</td>"
            f"</tr>"
        )
    return f"<table>{rows}</table>"


