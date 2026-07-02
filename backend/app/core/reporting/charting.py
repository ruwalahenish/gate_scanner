"""
charting.py
============
Interactive candlestick charts with signal and trade overlays using Plotly.

Signal chart : candlestick + EMA 20/50/100/200 + Entry / SL / T1-T3 levels + volume
Trade chart  : same layout + entry/exit markers + trailing-SL step-line

All charts are saved as self-contained HTML files that open in any browser.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from app.core.analysis import ema_engine

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------
_EMA_STYLE: Dict[int, dict] = {
    20:  dict(color="#FFD700", width=1.2),   # gold
    50:  dict(color="#FF8C00", width=1.2),   # dark-orange
    100: dict(color="#1E90FF", width=1.2),   # dodger-blue
    200: dict(color="#FF69B4", width=1.8),   # hot-pink (most important)
}

_CLR_ENTRY = "#2196F3"   # blue
_CLR_SL    = "#F44336"   # red
_CLR_T1    = "#81C784"   # light-green
_CLR_T2    = "#43A047"   # medium-green
_CLR_T3    = "#1B5E20"   # dark-green
_CLR_TRAIL = "#FF9800"   # orange

_UP_CLR   = "#26A69A"    # teal for bullish candles / volume
_DN_CLR   = "#EF5350"    # red  for bearish candles / volume
_BG_CLR   = "#1e1e2e"    # dark background


def _check_plotly() -> bool:
    if not PLOTLY_AVAILABLE:
        print(
            "\n[charting] Plotly is not installed. "
            "Run:  pip install plotly\n"
            "      Charts will be skipped.\n"
        )
        return False
    return True


def get_plotly_js_tag() -> str:
    """
    Return a <script> block containing plotly.min.js from the local installed package.
    Falls back to the CDN only if the local file cannot be found.

    Use this once in an HTML <head> to enable all embedded chart divs (built with
    include_plotlyjs=False) without requiring an internet connection.
    """
    if not PLOTLY_AVAILABLE:
        return ""
    try:
        import plotly as _plotly
        js_path = Path(_plotly.__file__).parent / "package_data" / "plotly.min.js"
        if js_path.exists():
            js = js_path.read_text(encoding="utf-8")
            return f'<script type="text/javascript">{js}</script>'
    except Exception:
        pass
    # fallback: CDN (requires internet)
    return '<script src="https://cdn.plot.ly/plotly-latest.min.js" charset="utf-8"></script>'


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _add_ema_traces(fig: "go.Figure", df: pd.DataFrame, row: int = 1) -> None:
    """Add EMA 20 / 50 / 100 / 200 lines to the given row."""
    ema_df = ema_engine.compute_emas(df)
    for period, style in _EMA_STYLE.items():
        col = f"EMA{period}"
        if col not in ema_df.columns:
            continue
        vals = ema_df[col]
        if vals.dropna().empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=vals,
                mode="lines",
                name=f"EMA{period}",
                line=style,
                hovertemplate=f"EMA{period}: ₹%{{y:.2f}}<extra></extra>",
            ),
            row=row, col=1,
        )


def _add_level_lines(
    fig: "go.Figure",
    levels: List[Tuple[Optional[float], str, str, str]],  # (price, color, label, dash)
    df_index: pd.DatetimeIndex,
) -> None:
    """
    Add horizontal price-level lines restricted to row 1 (price panel),
    with right-edge labels anchored just outside the chart boundary.
    """
    if df_index.empty:
        return
    x0 = df_index[0]
    x1 = df_index[-1]
    for price, color, label, dash in levels:
        if price is None:
            continue
        # Horizontal line — row=1, col=1 constrains it to the price panel
        fig.add_shape(
            type="line",
            x0=x0, x1=x1,
            y0=price, y1=price,
            line=dict(color=color, width=1.2, dash=dash),
            row=1, col=1,
        )
        # Right-edge annotation (paper x-coord so it stays outside the candles)
        fig.add_annotation(
            x=1.01, xref="paper",
            y=price, yref="y",
            text=label,
            showarrow=False,
            xanchor="left",
            font=dict(color=color, size=10),
            bgcolor="rgba(30,30,46,0.80)",
            borderpad=2,
        )


def _base_figure(df: pd.DataFrame, title: str) -> "go.Figure":
    """
    Build the base two-row figure: candlestick (row 1, 76%) + volume bars (row 2, 24%).
    Shared x-axis, dark theme.
    """
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.76, 0.24],
        vertical_spacing=0.02,
    )

    # ---- Candlestick ----
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"],   close=df["Close"],
            name="Price",
            increasing_line_color=_UP_CLR, increasing_fillcolor=_UP_CLR,
            decreasing_line_color=_DN_CLR, decreasing_fillcolor=_DN_CLR,
            hoverinfo="x+y",
        ),
        row=1, col=1,
    )

    # ---- Volume bars ----
    vol_colors = [
        _UP_CLR if c >= o else _DN_CLR
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df["Volume"],
            name="Volume",
            marker_color=vol_colors,
            showlegend=False,
            hovertemplate="Vol: %{y:,.0f}<extra></extra>",
        ),
        row=2, col=1,
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#e0e0e0")),
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        paper_bgcolor=_BG_CLR,
        plot_bgcolor=_BG_CLR,
        height=700,
        margin=dict(l=65, r=170, t=55, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.01,
            xanchor="left",   x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10),
        ),
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#2d2d3d", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#2d2d3d", zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# Signal chart  (scanner / --detail)
# ---------------------------------------------------------------------------

def build_signal_chart(
    symbol: str,
    ohlcv_df: pd.DataFrame,
    signal: Dict,
    out_path: str,
) -> Optional[str]:
    """
    Generate an interactive candlestick chart for a live scanner signal.

    Shows: last 120 bars of OHLCV, EMA 20/50/100/200, horizontal lines for
    Entry / SL / T1 / T2 / T3 with price and RR labels.

    Saves a self-contained HTML to *out_path* and returns the path.
    Returns None when Plotly is unavailable or data is insufficient.
    """
    if not _check_plotly():
        return None
    if ohlcv_df is None or len(ohlcv_df) < 10:
        return None

    df = ohlcv_df.tail(120).copy()

    side   = signal.get("side", "BUY")
    tf     = signal.get("signal_timeframe", "")
    gate   = signal.get("gate_strength", 0.0)
    conf   = signal.get("confidence", 0.0)
    entry  = signal.get("entry")
    sl     = signal.get("stop_loss")
    t1     = signal.get("T1")
    t2     = signal.get("T2")
    t3     = signal.get("T3")
    rr     = signal.get("rr", {})
    sl_pct = signal.get("sl_distance_pct", 0.0)

    title = (
        f"<b>{symbol}</b>  —  {side} ({tf})"
        f"  |  GATE {gate:.1f}"
        f"  |  Confidence {conf:.1f}%"
    )
    fig = _base_figure(df, title)
    _add_ema_traces(fig, df, row=1)

    levels: List[Tuple[Optional[float], str, str, str]] = [
        (entry, _CLR_ENTRY, f"Entry  ₹{entry:.2f}",                         "solid"),
        (sl,    _CLR_SL,    f"SL  ₹{sl:.2f}  (−{sl_pct:.1f}%)",             "dash"),
        (t1,    _CLR_T1,    f"T1  ₹{t1:.2f}  (RR {rr.get('T1', 0):.1f}×)",  "dot"),
        (t2,    _CLR_T2,    f"T2  ₹{t2:.2f}  (RR {rr.get('T2', 0):.1f}×)",  "dot"),
        (t3,    _CLR_T3,    f"T3  ₹{t3:.2f}  (RR {rr.get('T3', 0):.1f}×)",  "dot"),
    ]
    _add_level_lines(fig, levels, df.index)

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out_path, include_plotlyjs=True)
    return out_path
