"""
reporting.py
=============
Produces explainable output:

  * console table (rich)
  * CSV / JSON dumps
  * per-symbol detailed report
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH = True
except ImportError:
    RICH = False
    Console = None


# -----------------------------------------------------------------------------
# Console rendering
# -----------------------------------------------------------------------------
def print_summary(results: List[Dict]) -> None:
    """
    `results` is a list of dicts of shape:
       { "symbol": ..., "category": ..., "signal": {...} or None, "classification": {...} }
    """
    if not RICH:
        _print_plain(results)
        return

    console = Console()
    console.rule("[bold cyan]GATE Scanner — Results")

    # Group by category
    buckets = {}
    for r in results:
        cat = r["classification"]["category"]
        buckets.setdefault(cat, []).append(r)

    order = ["INVESTMENT", "SWING", "POSITIONAL", "WATCH", "IGNORE"]
    for cat in order:
        items = buckets.get(cat, [])
        if not items:
            continue
        # Sort within category by rank_score (if signal present)
        items.sort(
            key=lambda r: (r.get("signal") or {}).get("rank_score", 0),
            reverse=True,
        )
        table = Table(title=f"[bold]{cat}[/bold]  ({len(items)})",
                      show_lines=False, expand=True)
        table.add_column("Symbol", style="cyan")
        table.add_column("TF", justify="center")
        table.add_column("Action", justify="center")
        table.add_column("Entry", justify="right")
        table.add_column("SL", justify="right")
        table.add_column("T1", justify="right")
        table.add_column("T2", justify="right")
        table.add_column("T3", justify="right")
        table.add_column("RR(T2)", justify="right")
        table.add_column("GATE", justify="right")
        table.add_column("Conf%", justify="right")
        table.add_column("Score", justify="right", style="green")

        for r in items:
            s = r.get("signal") or {}
            table.add_row(
                r["symbol"],
                s.get("signal_timeframe", "-"),
                s.get("side", "-"),
                _fmt(s.get("entry")),
                _fmt(s.get("stop_loss")),
                _fmt(s.get("T1")),
                _fmt(s.get("T2")),
                _fmt(s.get("T3")),
                _fmt(s.get("rr", {}).get("T2") if s else None, dec=2),
                _fmt(s.get("gate_strength"), dec=1),
                _fmt(s.get("confidence"), dec=1),
                _fmt(s.get("rank_score"), dec=1),
            )
        console.print(table)


def _print_plain(results):
    print("\n=== GATE Scanner Results ===\n")
    for r in results:
        cat = r["classification"]["category"]
        s = r.get("signal")
        if s:
            print(f"[{cat:11}] {r['symbol']:10} {s['side']:5} {s['signal_timeframe']:4} "
                  f"entry={s['entry']:.2f} SL={s['stop_loss']:.2f} "
                  f"T1={s['T1']:.2f} T2={s['T2']:.2f} T3={s['T3']:.2f} "
                  f"GATE={s['gate_strength']:.1f} conf={s['confidence']:.1f}")
        else:
            print(f"[{cat:11}] {r['symbol']:10}  -  {r['classification']['reasoning']}")


def _fmt(v, dec=2):
    if v is None: return "-"
    try:
        return f"{float(v):.{dec}f}"
    except Exception:
        return str(v)


# -----------------------------------------------------------------------------
# File outputs
# -----------------------------------------------------------------------------
def write_csv(results: List[Dict], path: str) -> None:
    rows = []
    for r in results:
        s = r.get("signal") or {}
        rows.append({
            "symbol":            r["symbol"],
            "category":          r["classification"]["category"],
            "reasoning":         r["classification"]["reasoning"],
            "side":              s.get("side"),
            "signal_tf":         s.get("signal_timeframe"),
            "sl_tf":             s.get("sl_timeframe"),
            "entry":             s.get("entry"),
            "stop_loss":         s.get("stop_loss"),
            "T1":                s.get("T1"),
            "T2":                s.get("T2"),
            "T3":                s.get("T3"),
            "rr_T1":             (s.get("rr") or {}).get("T1"),
            "rr_T2":             (s.get("rr") or {}).get("T2"),
            "rr_T3":             (s.get("rr") or {}).get("T3"),
            "gate_strength":     s.get("gate_strength"),
            "vol_compression":   s.get("volatility_compression"),
            "breakout_prob":     s.get("breakout_probability"),
            "confidence":        s.get("confidence"),
            "rank_score":        s.get("rank_score"),
            "mtf_alignment_pct": s.get("mtf_alignment_pct"),
            "htf_confirmed":     s.get("htf_confirmed"),
            "phase":             s.get("phase"),
            "signal_reasoning":  s.get("reasoning"),
        })
    if not rows:
        Path(path).write_text("")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(results: List[Dict], path: str) -> None:
    # The full structure (including nested MTF analysis) can be huge; we keep
    # everything but make it JSON-safe.
    def _safe(o):
        if isinstance(o, dict):
            return {k: _safe(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [_safe(x) for x in o]
        if hasattr(o, "item"):       # numpy scalar
            try: return o.item()
            except Exception: return str(o)
        if isinstance(o, float) and (o != o):  # NaN
            return None
        return o

    Path(path).write_text(json.dumps(_safe(results), indent=2, default=str))


def detail_panel(result: Dict) -> None:
    """Pretty per-symbol detailed reasoning panel."""
    if not RICH:
        print(json.dumps(result, indent=2, default=str))
        return
    console = Console()
    s = result.get("signal") or {}
    title = f"[bold cyan]{result['symbol']}[/bold cyan]  —  {result['classification']['category']}"
    lines = [
        f"Classification: {result['classification']['reasoning']}",
        "",
    ]
    if s:
        lines.extend([
            f"Action: [bold]{s['side']}[/bold]   Signal TF: {s['signal_timeframe']}   SL TF: {s['sl_timeframe']}",
            f"Entry:  {s['entry']:.2f}    Stop Loss: {s['stop_loss']:.2f}  (SL dist {s['sl_distance_pct']:.2f}%)",
            f"T1: {s['T1']:.2f}  (RR {s['rr']['T1']:.2f})",
            f"T2: {s['T2']:.2f}  (RR {s['rr']['T2']:.2f})",
            f"T3: {s['T3']:.2f}  (RR {s['rr']['T3']:.2f})",
            f"GATE strength: {s['gate_strength']:.1f}   Breakout prob: {s['breakout_probability']:.1f}   Confidence: {s['confidence']:.1f}",
            f"MTF alignment: {s['mtf_alignment_pct']:.0f}%   HTF confirmed: {s['htf_confirmed']}",
            "",
            "[italic]Reasoning:[/italic]",
            s.get("reasoning", ""),
        ])
    console.print(Panel("\n".join(lines), title=title, expand=False))
