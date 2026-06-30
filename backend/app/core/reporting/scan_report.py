"""
scan_report.py
===============
Generate a self-contained modern HTML report for a live scanner run.

Usage (called automatically from ReportGenerationAgent.render):
    from app.core.reporting.scan_report import build_scan_report
    html_path = build_scan_report(results, out_dir, charts_dir, scan_meta)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_scan_report(
    results: List[Dict],
    out_dir: str | Path,
    charts_dir: Optional[str | Path] = None,
    scan_meta: Optional[Dict] = None,
) -> str:
    """Write scan_report.html to out_dir. Returns the file path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    charts_dir = Path(charts_dir) if charts_dir else out_dir / "charts"
    html = _build_html(results, charts_dir, out_dir, scan_meta or {})

    html_path = out_dir / "scan_report.html"
    html_path.write_text(html, encoding="utf-8")
    return str(html_path)


# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------

_CATEGORY_ORDER = ["INVESTMENT", "SWING", "POSITIONAL", "WATCH", "IGNORE"]

_CAT_COLORS = {
    "INVESTMENT": {"bg": "#d4af37", "text": "#1a1a2e", "badge": "#f5c518"},
    "SWING":      {"bg": "#00bcd4", "text": "#1a1a2e", "badge": "#26c6da"},
    "POSITIONAL": {"bg": "#5c6bc0", "text": "#fff",    "badge": "#7986cb"},
    "WATCH":      {"bg": "#78909c", "text": "#fff",    "badge": "#90a4ae"},
    "IGNORE":     {"bg": "#455a64", "text": "#cfd8dc", "badge": "#546e7a"},
}


def _fmt(v, dec: int = 2) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.{dec}f}"
    except Exception:
        return str(v)


def _pct_span(v) -> str:
    if v is None:
        return "—"
    try:
        fv = float(v)
        cls = "pos" if fv >= 0 else "neg"
        return f'<span class="{cls}">{fv:+.1f}%</span>'
    except Exception:
        return str(v)


def _build_html(
    results: List[Dict],
    charts_dir: Path,
    out_dir: Path,
    meta: Dict,
) -> str:
    from . import charting

    now_str    = meta.get("scan_time") or datetime.now().strftime("%Y-%m-%d %H:%M IST")
    universe   = meta.get("universe_size", len(results))
    timeframes = meta.get("timeframes", [])
    tf_str     = ", ".join(timeframes) if timeframes else "multi-TF"

    # Build buckets
    buckets: Dict[str, List[Dict]] = {c: [] for c in _CATEGORY_ORDER}
    for r in results:
        cat = r["classification"]["category"]
        buckets.setdefault(cat, []).append(r)

    # Sort within each bucket
    for cat, items in buckets.items():
        items.sort(key=lambda r: (r.get("signal") or {}).get("rank_score", 0), reverse=True)

    signal_count = sum(1 for r in results if r.get("signal"))
    inv_count    = len(buckets.get("INVESTMENT", []))
    sw_count     = len(buckets.get("SWING", []))
    pos_count    = len(buckets.get("POSITIONAL", []))

    stat_cards  = _stat_cards(universe, signal_count, inv_count, sw_count, pos_count)
    legend_html = _legend_section()
    sections    = "".join(
        _category_section(cat, buckets.get(cat, []), charts_dir, out_dir)
        for cat in _CATEGORY_ORDER
        if buckets.get(cat)
    )

    plotly_js_tag = charting.get_plotly_js_tag()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GATE Scanner Report — {now_str}</title>
{plotly_js_tag}
<style>
/* ── Reset & base ─────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #0f1117;
  color: #e0e0e0;
  font-size: 13px;
  line-height: 1.5;
}}
a {{ color: #64b5f6; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* ── Header ───────────────────────────────────────────────────── */
.header {{
  background: linear-gradient(135deg, #0d47a1 0%, #1a237e 50%, #0a1929 100%);
  padding: 28px 32px 22px;
  border-bottom: 2px solid #1565c0;
}}
.header-row {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}}
.header h1 {{
  font-size: 26px;
  font-weight: 700;
  color: #e3f2fd;
  letter-spacing: 1px;
}}
.header h1 span {{ color: #64b5f6; }}
.header-meta {{
  font-size: 12px;
  color: #90caf9;
  text-align: right;
}}
.header-meta strong {{ color: #bbdefb; }}

/* ── Search bar ───────────────────────────────────────────────── */
.search-bar {{
  padding: 12px 32px;
  background: #12151f;
  border-bottom: 1px solid #1e2a3a;
  display: flex;
  align-items: center;
  gap: 12px;
}}
.search-bar input {{
  background: #1e2a3a;
  border: 1px solid #2a3f5f;
  border-radius: 6px;
  color: #e0e0e0;
  padding: 7px 14px;
  font-size: 13px;
  width: 280px;
  outline: none;
}}
.search-bar input:focus {{ border-color: #42a5f5; }}
.search-bar label {{ color: #78909c; font-size: 12px; }}

/* ── Stats cards ──────────────────────────────────────────────── */
.stats {{
  display: flex;
  gap: 14px;
  padding: 20px 32px;
  flex-wrap: wrap;
  background: #12151f;
}}
.card {{
  background: #1a2035;
  border: 1px solid #1e2a3a;
  border-radius: 10px;
  padding: 14px 20px;
  min-width: 120px;
  flex: 1;
  max-width: 180px;
  text-align: center;
  transition: border-color .2s;
}}
.card:hover {{ border-color: #42a5f5; }}
.card-num {{
  font-size: 30px;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 4px;
}}
.card-label {{
  font-size: 11px;
  color: #78909c;
  text-transform: uppercase;
  letter-spacing: .5px;
}}
.card-scanned .card-num  {{ color: #e0e0e0; }}
.card-signals .card-num  {{ color: #64b5f6; }}
.card-invest  .card-num  {{ color: #f5c518; }}
.card-swing   .card-num  {{ color: #26c6da; }}
.card-pos     .card-num  {{ color: #7986cb; }}

/* ── Main content ─────────────────────────────────────────────── */
.content {{ padding: 20px 32px 40px; }}

/* ── Category section ─────────────────────────────────────────── */
.cat-section {{ margin-bottom: 32px; }}
.cat-header {{
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  cursor: pointer;
  user-select: none;
}}
.cat-badge {{
  display: inline-block;
  padding: 3px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .5px;
}}
.cat-title {{
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
}}
.cat-count {{
  font-size: 12px;
  color: #78909c;
}}
.cat-toggle {{
  margin-left: auto;
  color: #546e7a;
  font-size: 16px;
  transition: transform .2s;
}}
.cat-section.collapsed .cat-toggle {{ transform: rotate(-90deg); }}
.cat-body {{ overflow: hidden; transition: max-height .3s ease; }}

/* ── Signal table ─────────────────────────────────────────────── */
.sig-table {{
  width: 100%;
  border-collapse: collapse;
  background: #1a2035;
  border-radius: 8px;
  overflow: hidden;
}}
.sig-table th {{
  background: #0d47a1;
  color: #bbdefb;
  padding: 9px 10px;
  font-size: 11px;
  font-weight: 600;
  text-align: right;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}}
.sig-table th:first-child,
.sig-table th:nth-child(2),
.sig-table th:nth-child(3),
.sig-table th:nth-child(4) {{ text-align: left; }}
.sig-table th:hover {{ background: #1565c0; }}
.sig-table th .sort-arrow {{ margin-left: 4px; opacity: .4; }}
.sig-table th.sorted-asc .sort-arrow::after  {{ content: "▲"; opacity: 1; }}
.sig-table th.sorted-desc .sort-arrow::after {{ content: "▼"; opacity: 1; }}
.sig-table td {{
  padding: 8px 10px;
  border-bottom: 1px solid #1e2a3a;
  text-align: right;
  white-space: nowrap;
  vertical-align: middle;
}}
.sig-table td:first-child,
.sig-table td:nth-child(2),
.sig-table td:nth-child(3),
.sig-table td:nth-child(4) {{ text-align: left; }}
.sig-table tr:last-child td {{ border-bottom: none; }}
.sig-table tr:hover td {{ background: #1e2a4a; }}

/* Symbol cell */
.sym-cell {{ font-weight: 600; font-size: 13px; letter-spacing: .3px; }}
.sym-cell a {{ color: #90caf9; }}

/* Action badge */
.action-buy  {{ color: #26a69a; font-weight: 700; font-size: 12px; }}
.action-sell {{ color: #ef5350; font-weight: 700; font-size: 12px; }}

/* Gate/confidence bar */
.bar-wrap {{
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: flex-end;
}}
.bar-bg {{
  width: 48px;
  height: 6px;
  background: #263238;
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
}}
.bar-fill {{ height: 100%; border-radius: 3px; }}
.bar-val {{ font-size: 12px; min-width: 30px; text-align: right; }}

/* Positive / negative spans */
.pos {{ color: #66bb6a; font-weight: 600; }}
.neg {{ color: #ef5350; font-weight: 600; }}

/* HTF confirmed */
.htf-yes {{ color: #26a69a; font-size: 11px; }}
.htf-no  {{ color: #546e7a; font-size: 11px; }}

/* Reasoning tooltip */
.reason-cell {{
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #78909c;
  font-size: 11px;
  text-align: left !important;
  cursor: default;
}}

/* Score pill */
.score-pill {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 700;
}}

/* Watch/Ignore simplified table */
.watch-table {{
  width: 100%;
  border-collapse: collapse;
  background: #1a2035;
  border-radius: 8px;
  overflow: hidden;
}}
.watch-table th {{
  background: #1e2a3a;
  color: #78909c;
  padding: 8px 10px;
  font-size: 11px;
  text-align: left;
}}
.watch-table td {{
  padding: 7px 10px;
  border-bottom: 1px solid #1e2a3a;
  font-size: 12px;
  color: #90a4ae;
}}
.watch-table tr:last-child td {{ border-bottom: none; }}
.watch-table tr:hover td {{ background: #1e2a4a; }}

/* ── Footer ───────────────────────────────────────────────────── */
.footer {{
  text-align: center;
  padding: 20px;
  color: #37474f;
  font-size: 11px;
  border-top: 1px solid #1e2a3a;
}}

/* ── Legend / Column Reference ────────────────────────────────── */
.legend-section {{
  background: #12151f;
  border-bottom: 1px solid #1e2a3a;
}}
.legend-hdr {{
  display: flex; align-items: center; gap: 12px;
  padding: 13px 32px; cursor: pointer; user-select: none;
  transition: background .15s;
}}
.legend-hdr:hover {{ background: #161925; }}
.legend-hdr-icon {{
  width: 26px; height: 26px;
  background: linear-gradient(135deg, #1565c0 0%, #6a1b9a 100%);
  border-radius: 6px; display: flex; align-items: center;
  justify-content: center; font-size: 13px; flex-shrink: 0;
}}
.legend-hdr-title {{ font-size: 13px; font-weight: 600; color: #90caf9; }}
.legend-hdr-sub   {{ font-size: 11px; color: #546e7a; margin-left: 4px; }}
.legend-toggle    {{
  margin-left: auto; color: #546e7a; font-size: 14px;
  transition: transform .25s;
}}
.legend-section.collapsed .legend-toggle {{ transform: rotate(-90deg); }}
.legend-body {{ overflow: hidden; max-height: 0; transition: max-height .4s ease; }}
.legend-inner {{ padding: 4px 32px 28px; }}
.legend-group-title {{
  font-size: 10px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: #546e7a;
  margin: 22px 0 10px; padding-bottom: 6px;
  border-bottom: 1px solid #1e2a3a;
}}
.legend-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: 10px;
}}
.col-card {{
  background: #1a2035; border: 1px solid #1e2a3a;
  border-radius: 10px; padding: 13px 15px;
  transition: border-color .2s, box-shadow .2s;
}}
.col-card:hover {{
  border-color: #42a5f5;
  box-shadow: 0 0 0 1px rgba(66,165,245,.15), 0 4px 16px rgba(0,0,0,.4);
}}
.col-card-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 9px; }}
.col-badge {{
  display: inline-block; background: #0d47a1; color: #90caf9;
  font-size: 11px; font-weight: 700; padding: 2px 9px;
  border-radius: 4px; letter-spacing: .3px;
}}
.col-badge.scoring {{ background: #1b5e20; color: #a5d6a7; }}
.col-badge.filter  {{ background: #7b1fa2; color: #e1bee7; }}
.col-range {{
  margin-left: auto; font-size: 10px; color: #546e7a;
  background: #0f1117; padding: 2px 7px; border-radius: 3px;
}}
.col-desc {{ font-size: 12px; color: #90a4ae; line-height: 1.55; margin-bottom: 9px; }}
.col-formula {{
  background: #0d1117; border-left: 3px solid #1565c0;
  border-radius: 0 4px 4px 0; padding: 7px 10px;
  font-family: 'Consolas', 'Fira Code', 'Courier New', monospace;
  font-size: 11px; color: #80cbc4; white-space: pre-wrap;
  word-break: break-all; line-height: 1.6;
}}
.col-formula.warn  {{ border-left-color: #f57f17; color: #ffe082; }}
.col-formula.score {{ border-left-color: #2e7d32; color: #a5d6a7; }}
.col-thresholds {{ display: flex; flex-wrap: wrap; gap: 5px; margin-top: 9px; }}
.threshold-pill {{
  font-size: 10px; padding: 2px 8px; border-radius: 12px; font-weight: 600;
}}
.pill-green  {{ background: #1b5e20; color: #a5d6a7; }}
.pill-blue   {{ background: #0d47a1; color: #90caf9; }}
.pill-orange {{ background: #e65100; color: #ffcc80; }}
.pill-red    {{ background: #b71c1c; color: #ffcdd2; }}
.pill-grey   {{ background: #263238; color: #90a4ae; }}
.pill-gold   {{ background: #4a3700; color: #f5c518; }}
/* GATE components */
.gate-breakdown {{
  background: #1a2035; border: 1px solid #1e2a3a;
  border-radius: 8px; padding: 14px; margin-top: 10px;
}}
.gate-breakdown-title {{
  font-size: 11px; font-weight: 700; color: #f5c518;
  letter-spacing: .5px; text-transform: uppercase; margin-bottom: 10px;
}}
.gate-comp-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px;
}}
.gate-comp {{
  background: #0f1117; border-radius: 6px; padding: 9px 10px;
  border: 1px solid #1e2a3a;
}}
.gate-comp-header {{ display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }}
.gate-comp-name   {{ font-size: 11px; font-weight: 600; color: #e0e0e0; }}
.gate-comp-weight {{
  margin-left: auto; font-size: 10px; font-weight: 700;
  background: #1a2744; color: #64b5f6;
  padding: 1px 7px; border-radius: 10px;
}}
.gate-comp-trigger {{ font-size: 10px; color: #78909c; line-height: 1.5; }}
/* Confidence multiplier mini-table */
.mult-table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 11px; }}
.mult-table th {{
  background: #0f1117; color: #546e7a; padding: 5px 8px;
  text-align: left; font-size: 10px; font-weight: 600; letter-spacing: .5px;
}}
.mult-table td {{ padding: 5px 8px; border-bottom: 1px solid #1e2a3a; color: #b0bec5; }}
.mult-table tr:last-child td {{ border-bottom: none; }}
.mult-plus  {{ color: #66bb6a; font-weight: 700; }}
.mult-minus {{ color: #ef5350; font-weight: 700; }}
/* SL map mini-table */
.sl-map-table {{ width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 8px; }}
.sl-map-table td {{ padding: 4px 8px; border-bottom: 1px solid #1e2a3a; }}
.sl-map-table tr:last-child td {{ border-bottom: none; }}
.sl-map-table .tf-col  {{ font-weight: 600; color: #64b5f6; }}
.sl-map-table .arr-col {{ color: #546e7a; text-align: center; }}
.sl-map-table .sl-col  {{ color: #ef9a9a; font-size: 10.5px; }}
/* Category pills row */
.cat-pills {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
.cat-pill {{
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 8px; font-size: 11px; font-weight: 600;
}}
.cat-pill-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
</style>
</head>
<body>

<!-- ── Header ─────────────────────────────────────────────────── -->
<div class="header">
  <div class="header-row">
    <div>
      <h1>GATE <span>Scanner</span> Report</h1>
    </div>
    <div class="header-meta">
      <div><strong>Scan Time:</strong> {now_str}</div>
      <div><strong>Universe:</strong> {universe} symbols &nbsp;|&nbsp; <strong>Timeframes:</strong> {tf_str}</div>
    </div>
  </div>
</div>

<!-- ── Search bar ─────────────────────────────────────────────── -->
<div class="search-bar">
  <input type="text" id="search-input" placeholder="Search symbol…" oninput="filterTable(this.value)">
  <label>Filter symbols across all tables</label>
</div>

<!-- ── Column Reference Legend ────────────────────────────────── -->
{legend_html}

<!-- ── Stats cards ────────────────────────────────────────────── -->
<div class="stats">
{stat_cards}
</div>

<!-- ── Main content ───────────────────────────────────────────── -->
<div class="content" id="main-content">
{sections}
</div>

<!-- ── Footer ─────────────────────────────────────────────────── -->
<div class="footer">Generated by GATE Scanner · {now_str}</div>

<script>
// ── Sort ───────────────────────────────────────────────────────
function sortTable(th) {{
  var table = th.closest('table');
  var idx   = Array.from(th.parentNode.children).indexOf(th);
  var asc   = !th.classList.contains('sorted-asc');
  th.parentNode.querySelectorAll('th').forEach(function(t) {{
    t.classList.remove('sorted-asc', 'sorted-desc');
  }});
  th.classList.add(asc ? 'sorted-asc' : 'sorted-desc');

  var tbody = table.querySelector('tbody');
  var rows  = Array.from(tbody.querySelectorAll('tr'));
  rows.sort(function(a, b) {{
    var va = a.cells[idx] ? a.cells[idx].getAttribute('data-val') || a.cells[idx].textContent.trim() : '';
    var vb = b.cells[idx] ? b.cells[idx].getAttribute('data-val') || b.cells[idx].textContent.trim() : '';
    var na = parseFloat(va), nb = parseFloat(vb);
    if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
    return asc ? va.localeCompare(vb) : vb.localeCompare(va);
  }});
  rows.forEach(function(r) {{ tbody.appendChild(r); }});
}}

// ── Toggle section ─────────────────────────────────────────────
function toggleSection(el) {{
  var section = el.closest('.cat-section');
  section.classList.toggle('collapsed');
  var body = section.querySelector('.cat-body');
  if (section.classList.contains('collapsed')) {{
    body.style.maxHeight = '0';
  }} else {{
    body.style.maxHeight = body.scrollHeight + 'px';
  }}
}}

// Initialise all sections open
document.querySelectorAll('.cat-body').forEach(function(b) {{
  b.style.maxHeight = b.scrollHeight + 'px';
}});

// ── Legend toggle ──────────────────────────────────────────────
function toggleLegend() {{
  var sec  = document.getElementById('legend-section');
  var body = document.getElementById('legend-body');
  if (!sec || !body) return;
  var isOpen = body.style.maxHeight && body.style.maxHeight !== '0px';
  if (isOpen) {{
    body.style.maxHeight = '0';
    sec.classList.add('collapsed');
  }} else {{
    body.style.maxHeight = body.scrollHeight + 'px';
    sec.classList.remove('collapsed');
  }}
}}

// ── Filter ─────────────────────────────────────────────────────
function filterTable(q) {{
  q = q.toLowerCase().trim();
  document.querySelectorAll('.sig-table tbody tr, .watch-table tbody tr').forEach(function(row) {{
    var sym = (row.cells[0] ? row.cells[0].textContent : '').toLowerCase();
    row.style.display = (!q || sym.includes(q)) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Column Reference Legend
# ---------------------------------------------------------------------------

def _legend_section() -> str:
    """Return the full 'Column Reference' collapsible HTML block."""

    # ── Signal column cards ───────────────────────────────────────
    symbol_card = _col_card(
        "Symbol", "signal", "0 – 100", "",
        "NSE ticker (no .NS suffix). BSE-only stocks show .BO suffix "
        "(e.g. ZENSARTECH.BO). Symbols with & or - are normalised internally.",
        "",
    )

    tf_card = _col_card(
        "TF", "signal", "1m → 1mo", "",
        "Confirmation timeframe — one step higher than the leading TF where the "
        "GATE first fired. Entry signal is generated here.",
        "Leading TF  = smallest TF with GATE ≥ 55 or BP ≥ 60\n"
        "Confirm TF  = next-larger TF in hierarchy\n"
        "Hierarchy : 1m→3m→5m→15m→30m→60m→4h→1d→1wk→1mo",
    )

    action_card = _col_card(
        "Action", "signal", "BUY / SELL", "",
        "Trade direction from a majority 3-vote system per timeframe: "
        "(1) EMA stack, (2) EMA50+100 slope, (3) close vs mid-Bollinger Band. "
        "Dominant direction across all TFs wins.",
        "BUY  when dominant direction = up\n"
        "SELL when dominant direction = down",
    )

    phase_card = _col_card(
        "Phase", "signal", "4 states", "",
        "Current market phase of the signal TF.",
        "contracting  → EMA spread &lt; 4% &amp; tightening (GATE forming)\n"
        "correcting   → price or time pullback to an EMA\n"
        "trending     → EMA slopes aligned, ADX ≥ 25\n"
        "transitioning→ no dominant state",
    )

    entry_card = _col_card(
        "Entry", "signal", "&gt; ₹20", "filter",
        "Current close price of the confirmation TF. No markup added. "
        "Signals with Entry &lt; ₹20 are rejected (penny-stock filter).",
        "Entry = Close[-1]  of confirmation TF",
    )

    sl_card = (
        '<div class="col-card">'
        '<div class="col-card-header">'
        '<span class="col-badge filter">SL</span>'
        '<span class="col-range">SL dist ≤ 12%</span>'
        '</div>'
        '<div class="col-desc">Stop loss = EMA200 of the next-smaller timeframe. '
        'ATR fallback when smaller-TF data is unavailable. '
        'Rejected if SL distance &gt; 12% of entry.</div>'
        '<div class="col-formula">SL = EMA200 of SL_TF\n'
        'ATR fallback: Entry ± 2×ATR(14)\n\n'
        'SL_TF map:\n'
        '</div>'
        '<table class="sl-map-table">'
        '<tr><td class="tf-col">1d</td><td class="arr-col">→</td><td class="sl-col">4h EMA200</td></tr>'
        '<tr><td class="tf-col">1wk</td><td class="arr-col">→</td><td class="sl-col">1d EMA200</td></tr>'
        '<tr><td class="tf-col">4h</td><td class="arr-col">→</td><td class="sl-col">60m EMA200</td></tr>'
        '<tr><td class="tf-col">60m</td><td class="arr-col">→</td><td class="sl-col">15m EMA200</td></tr>'
        '<tr><td class="tf-col">15m</td><td class="arr-col">→</td><td class="sl-col">5m EMA200</td></tr>'
        '</table>'
        '<div class="col-thresholds">'
        '<span class="threshold-pill pill-red">Rejected if &gt; 12%</span>'
        '</div>'
        '</div>'
    )

    targets_card = _col_card(
        "T1 / T2 / T3", "signal", "₹ targets", "",
        "ATR-projected near target (T1) plus strategy expectancy table for T2/T3. "
        "T1 may snap to swing-high/low between T1 and T2.",
        "T1 = max(Entry+2×ATR,  Entry×(1+low_pct×0.25))\n"
        "T2 = Entry × (1 + mid_pct)\n"
        "T3 = Entry × (1 + high_pct)\n\n"
        "1d: low=50% high=70%  |  4h: 35–40%\n"
        "60m: 20–25%  |  15m: 7–10%  |  5m: 5–7%",
    )

    rr_card = _col_card(
        "RR(T2)", "signal", "≥ 1.5×", "filter",
        "Reward-to-risk ratio measured at T2. Signals with RR(T1) &lt; 1.5 are "
        "rejected entirely.",
        "BUY : RR = (T2 − Entry) / (Entry − SL)\n"
        "SELL: RR = (Entry − T2) / (SL − Entry)",
    )

    # ── GATE card (special — with component grid) ─────────────────
    gate_card = (
        '<div class="col-card" style="grid-column: 1 / -1;">'
        '<div class="col-card-header">'
        '<span class="col-badge scoring">GATE</span>'
        '<span class="col-range">0 – 100</span>'
        '</div>'
        '<div class="col-desc">6-component weighted volatility contraction score. '
        'Measures how tightly compressed a stock is before an explosive expansion move. '
        '<strong style="color:#f5c518">≥ 55</strong> = active GATE (signal generated). '
        '<strong style="color:#f5c518">≥ 70</strong> = strong GATE.</div>'
        '<div class="col-formula score">GATE = 100 × Σ( component_score[i] × weight[i] )</div>'
        '<div class="gate-breakdown">'
        '<div class="gate-breakdown-title">⚡ 6 GATE Components</div>'
        '<div class="gate-comp-grid">'
        + _gate_comp("BB Squeeze", "22%",
                     "BB width ≤ 20th pctile of last 100 bars",
                     "score = 1 − rank/20  if rank ≤ 20%")
        + _gate_comp("ATR Contraction", "18%",
                     "ATR(14) ≤ 25th pctile of last 100 bars",
                     "score = 1 − rank/25  if rank ≤ 25%")
        + _gate_comp("EMA Compression", "22%",
                     "(EMA_max−EMA_min)/price ≤ 8%",
                     "score = max(0, 1 − spread/0.08)")
        + _gate_comp("Narrow Range", "13%",
                     "Avg range of last 5 candles ≤ 60% of ATR",
                     "score = max(0, min(1, (1−ratio)/0.4))")
        + _gate_comp("Volume Contraction", "13%",
                     "10-bar vol avg &lt; 70% of 50-bar avg",
                     "score = max(0, min(1, (1−ratio)/0.6))")
        + _gate_comp("ADX Contraction", "12%",
                     "ADX(14) ≤ 15 → score=1.0;  ADX ≥ 35 → 0.0",
                     "score = 1 − (ADX−15)/(35−15)  between")
        + '</div></div>'
        '<div class="col-thresholds">'
        '<span class="threshold-pill pill-gold">≥ 70 Strong GATE</span>'
        '<span class="threshold-pill pill-green">≥ 55 Active GATE</span>'
        '<span class="threshold-pill pill-grey">&lt; 55 Sub-threshold</span>'
        '</div>'
        '</div>'
    )

    # ── Confidence card ───────────────────────────────────────────
    conf_card = (
        '<div class="col-card">'
        '<div class="col-card-header">'
        '<span class="col-badge scoring">Conf%</span>'
        '<span class="col-range">0 – 100</span>'
        '</div>'
        '<div class="col-desc">Composite signal quality score. Combines GATE, MTF alignment, '
        'structure quality, and breakout probability — then adjusts via quality multipliers.</div>'
        '<div class="col-formula score">'
        'base = 0.30×GATE + 0.25×MTF%\n'
        '     + 0.20×StructQuality + 0.25×BreakoutProb\n'
        'Conf% = min(100, base × multiplier)'
        '</div>'
        '<table class="mult-table">'
        '<tr><th>Condition</th><th>Multiplier</th></tr>'
        '<tr><td>HTF confirmed</td><td><span class="mult-plus">+10%</span></td></tr>'
        '<tr><td>Fake correction (EMA200 not touched)</td><td><span class="mult-minus">−10%</span></td></tr>'
        '<tr><td>Bounce sequence invalid (EMAs skipped)</td><td><span class="mult-minus">−8%</span></td></tr>'
        '<tr><td>Fibonacci confluence (38.2/50/61.8%)</td><td><span class="mult-plus">+8%</span></td></tr>'
        '</table>'
        '</div>'
    )

    mtf_card = _col_card(
        "MTF%", "scoring", "0 – 100", "",
        "Percentage of analysed timeframes that agree on the dominant direction. "
        "Each TF casts 3 votes: EMA stack + slope direction + GATE bias (close vs mid-BB).",
        "MTF% = aligned_TFs / total_TFs × 100\n\n"
        "e.g. 60m=up, 4h=up, 1d=up, 1wk=up, 1mo=down\n"
        "  →  MTF% = 4/5 × 100 = 80%",
    )

    htf_card = _col_card(
        "HTF", "scoring", "Yes / No", "",
        "Higher-Timeframe Confirmation. True when the confirmation TF direction "
        "matches the leading TF direction. Adds 8% bonus to the rank Score.",
        "Leading TF     = smallest TF with GATE≥55 or BP≥60\n"
        "Confirm TF     = next-larger TF\n"
        "HTF = Yes if both directions agree (non-neutral)",
    )

    score_card = _col_card(
        "Score", "scoring", "0 – 100", "",
        "Final rank score used to sort signals within each category. "
        "Higher = listed first. HTF confirmation multiplies by 1.08.",
        "Score = (0.30×GATE + 0.25×MTF%\n"
        "       + 0.20×StructQuality + 0.15×BP\n"
        "       + 0.10×RR_norm) × 1.08 if HTF\n\n"
        "RR_norm = min(RR_T2/5, 1.0) × 100",
    )

    reasoning_card = _col_card(
        "Reasoning", "signal", "narrative", "",
        "Auto-generated one-paragraph narrative covering: EMA stack &amp; phase, "
        "GATE components, correction type/depth, quality warnings (fake correction / "
        "skipped EMAs), Fibonacci confluence, correction maturity, and MTF summary.",
        "",
    )

    # ── Category reference ────────────────────────────────────────
    cat_pills = (
        '<div class="cat-pills">'
        '<div class="cat-pill" style="background:#2a2200">'
        '<div class="cat-pill-dot" style="background:#f5c518"></div>'
        '<div><strong style="color:#f5c518">INVESTMENT</strong>'
        '<div style="font-size:10px;color:#78909c;margin-top:1px">Weekly+Monthly bullish · Score ≥ 70</div></div>'
        '</div>'
        '<div class="cat-pill" style="background:#002933">'
        '<div class="cat-pill-dot" style="background:#26c6da"></div>'
        '<div><strong style="color:#26c6da">SWING</strong>'
        '<div style="font-size:10px;color:#78909c;margin-top:1px">Daily bullish · GATE ≥ 60 · Score ≥ 60</div></div>'
        '</div>'
        '<div class="cat-pill" style="background:#1a1a3e">'
        '<div class="cat-pill-dot" style="background:#7986cb"></div>'
        '<div><strong style="color:#7986cb">POSITIONAL</strong>'
        '<div style="font-size:10px;color:#78909c;margin-top:1px">60m bullish · GATE ≥ 50 · Score ≥ 50</div></div>'
        '</div>'
        '<div class="cat-pill" style="background:#1a2235">'
        '<div class="cat-pill-dot" style="background:#90a4ae"></div>'
        '<div><strong style="color:#90a4ae">WATCH</strong>'
        '<div style="font-size:10px;color:#78909c;margin-top:1px">GATE ≥ 55 · no breakout yet</div></div>'
        '</div>'
        '<div class="cat-pill" style="background:#111">'
        '<div class="cat-pill-dot" style="background:#546e7a"></div>'
        '<div><strong style="color:#546e7a">IGNORE</strong>'
        '<div style="font-size:10px;color:#78909c;margin-top:1px">Bearish structure or RR below min</div></div>'
        '</div>'
        '</div>'
    )

    # ── Assemble ──────────────────────────────────────────────────
    return (
        '<div class="legend-section collapsed" id="legend-section">'
        '<div class="legend-hdr" onclick="toggleLegend()">'
        '<div class="legend-hdr-icon">📖</div>'
        '<span class="legend-hdr-title">Column Reference</span>'
        '<span class="legend-hdr-sub">— click to expand formula &amp; logic guide</span>'
        '<span class="legend-toggle" id="legend-toggle">▼</span>'
        '</div>'
        '<div class="legend-body" id="legend-body">'
        '<div class="legend-inner">'

        '<div class="legend-group-title">📍 Signal Columns</div>'
        '<div class="legend-grid">'
        + symbol_card + tf_card + action_card + phase_card
        + entry_card + sl_card + targets_card + rr_card
        + '</div>'

        '<div class="legend-group-title">📊 Scoring &amp; Classification</div>'
        + gate_card
        + '<div class="legend-grid" style="margin-top:10px">'
        + conf_card + mtf_card + htf_card + score_card + reasoning_card
        + '</div>'

        '<div class="legend-group-title">🏷️ Signal Categories</div>'
        + cat_pills

        + '</div>'  # legend-inner
        '</div>'    # legend-body
        '</div>'    # legend-section
    )


def _col_card(name: str, badge_type: str, range_str: str, extra_cls: str,
              desc: str, formula: str) -> str:
    cls = f"col-badge {badge_type}" if badge_type in ("scoring", "filter") else "col-badge"
    if extra_cls:
        cls = f"col-badge {extra_cls}"
    formula_html = (
        f'<div class="col-formula">{formula}</div>' if formula else ""
    )
    return (
        f'<div class="col-card">'
        f'<div class="col-card-header">'
        f'<span class="{cls}">{name}</span>'
        f'<span class="col-range">{range_str}</span>'
        f'</div>'
        f'<div class="col-desc">{desc}</div>'
        f'{formula_html}'
        f'</div>'
    )


def _gate_comp(name: str, weight: str, trigger: str, formula: str) -> str:
    return (
        f'<div class="gate-comp">'
        f'<div class="gate-comp-header">'
        f'<span class="gate-comp-name">{name}</span>'
        f'<span class="gate-comp-weight">{weight}</span>'
        f'</div>'
        f'<div class="gate-comp-trigger">{trigger}<br>'
        f'<span style="color:#546e7a;font-family:monospace">{formula}</span></div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Stat cards
# ---------------------------------------------------------------------------

def _stat_cards(universe, signals, invest, swing, pos) -> str:
    return f"""
  <div class="card card-scanned">
    <div class="card-num">{universe}</div>
    <div class="card-label">Scanned</div>
  </div>
  <div class="card card-signals">
    <div class="card-num">{signals}</div>
    <div class="card-label">Signals</div>
  </div>
  <div class="card card-invest">
    <div class="card-num">{invest}</div>
    <div class="card-label">Investment</div>
  </div>
  <div class="card card-swing">
    <div class="card-num">{swing}</div>
    <div class="card-label">Swing</div>
  </div>
  <div class="card card-pos">
    <div class="card-num">{pos}</div>
    <div class="card-label">Positional</div>
  </div>"""


# ---------------------------------------------------------------------------
# Per-category section
# ---------------------------------------------------------------------------

def _category_section(cat: str, items: List[Dict], charts_dir: Path, out_dir: Path) -> str:
    if not items:
        return ""

    colors = _CAT_COLORS.get(cat, {"bg": "#546e7a", "text": "#fff", "badge": "#546e7a"})
    badge  = (
        f'<span class="cat-badge" '
        f'style="background:{colors["bg"]};color:{colors["text"]}">'
        f'{cat}</span>'
    )

    if cat in ("WATCH", "IGNORE"):
        body = _watch_table(items)
    else:
        body = _signal_table(items, charts_dir, out_dir)

    return f"""
<div class="cat-section" id="section-{cat.lower()}">
  <div class="cat-header" onclick="toggleSection(this)">
    {badge}
    <span class="cat-title">{cat.title()}</span>
    <span class="cat-count">— {len(items)} symbol{"s" if len(items) != 1 else ""}</span>
    <span class="cat-toggle">▼</span>
  </div>
  <div class="cat-body">
    {body}
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Full signal table (INVESTMENT / SWING / POSITIONAL)
# ---------------------------------------------------------------------------

def _signal_table(items: List[Dict], charts_dir: Path, out_dir: Path) -> str:
    header = """
    <tr>
      <th onclick="sortTable(this)">Symbol<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">TF<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">Action<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">Phase<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">Entry<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">SL<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">T1<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">T2<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">T3<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">RR(T2)<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">GATE<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">Conf%<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">MTF%<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">HTF<span class="sort-arrow"></span></th>
      <th onclick="sortTable(this)">Score<span class="sort-arrow"></span></th>
      <th>Reasoning</th>
    </tr>"""

    rows = ""
    for r in items:
        s = r.get("signal") or {}
        sym = r["symbol"]

        # Chart link
        tf = s.get("signal_timeframe", "1d")
        chart_file = charts_dir / f"{sym}_{tf}.html"
        rel_path = _rel_path(chart_file, out_dir)
        sym_cell = (
            f'<a href="{rel_path}" target="_blank">{sym}</a>'
            if chart_file.exists()
            else sym
        )

        action   = s.get("side", "—")
        act_cls  = "action-buy" if action == "BUY" else ("action-sell" if action == "SELL" else "")
        rr_t2    = (s.get("rr") or {}).get("T2")
        gate     = s.get("gate_strength")
        conf     = s.get("confidence")
        score    = s.get("rank_score")
        mtf      = s.get("mtf_alignment_pct")
        htf_ok   = s.get("htf_confirmed", False)
        phase    = s.get("phase") or "—"
        reasoning = (s.get("reasoning") or r["classification"].get("reasoning", "")).replace('"', '&quot;')

        gate_bar  = _mini_bar(gate,  "#f5c518") if gate  is not None else "—"
        conf_bar  = _mini_bar(conf,  "#42a5f5") if conf  is not None else "—"
        score_pill = _score_pill(score)

        htf_html = (
            '<span class="htf-yes">✔ Yes</span>'
            if htf_ok else
            '<span class="htf-no">No</span>'
        )

        rows += f"""
    <tr>
      <td class="sym-cell">{sym_cell}</td>
      <td>{tf}</td>
      <td class="{act_cls}">{action}</td>
      <td>{phase}</td>
      <td data-val="{s.get("entry") or 0}">{_fmt(s.get("entry"))}</td>
      <td data-val="{s.get("stop_loss") or 0}">{_fmt(s.get("stop_loss"))}</td>
      <td data-val="{s.get("T1") or 0}">{_fmt(s.get("T1"))}</td>
      <td data-val="{s.get("T2") or 0}">{_fmt(s.get("T2"))}</td>
      <td data-val="{s.get("T3") or 0}">{_fmt(s.get("T3"))}</td>
      <td data-val="{rr_t2 or 0}">{_fmt(rr_t2)}</td>
      <td>{gate_bar}</td>
      <td>{conf_bar}</td>
      <td data-val="{mtf or 0}">{_fmt(mtf, 0)}%</td>
      <td>{htf_html}</td>
      <td>{score_pill}</td>
      <td class="reason-cell" title="{reasoning}">{reasoning[:60]}{"…" if len(reasoning) > 60 else ""}</td>
    </tr>"""

    return f'<table class="sig-table"><thead>{header}</thead><tbody>{rows}</tbody></table>'


# ---------------------------------------------------------------------------
# Simplified table for WATCH / IGNORE
# ---------------------------------------------------------------------------

def _watch_table(items: List[Dict]) -> str:
    header = """
    <tr>
      <th>Symbol</th>
      <th>Category</th>
      <th>Reasoning</th>
    </tr>"""

    rows = ""
    for r in items:
        cat = r["classification"]["category"]
        reasoning = r["classification"].get("reasoning", "—")
        rows += f"""
    <tr>
      <td style="font-weight:600">{r["symbol"]}</td>
      <td>{cat}</td>
      <td class="reason-cell" title="{reasoning}">{reasoning[:100]}{"…" if len(reasoning) > 100 else ""}</td>
    </tr>"""

    return f'<table class="watch-table"><thead>{header}</thead><tbody>{rows}</tbody></table>'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mini_bar(value, color: str) -> str:
    """Renders a mini progress bar + numeric label for 0–100 values."""
    try:
        pct = max(0, min(100, float(value)))
    except (TypeError, ValueError):
        return "—"
    return (
        f'<div class="bar-wrap">'
        f'<span class="bar-val">{pct:.1f}</span>'
        f'<div class="bar-bg"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'
        f'</div>'
    )


def _score_pill(value) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    if v >= 75:
        bg, fg = "#1b5e20", "#a5d6a7"
    elif v >= 55:
        bg, fg = "#0d47a1", "#90caf9"
    elif v >= 35:
        bg, fg = "#37474f", "#cfd8dc"
    else:
        bg, fg = "#212121", "#757575"
    return f'<span class="score-pill" style="background:{bg};color:{fg}">{v:.1f}</span>'


def _rel_path(target: Path, base_dir: Path) -> str:
    """Return a relative URL from base_dir to target (forward slashes)."""
    try:
        return target.relative_to(base_dir).as_posix()
    except ValueError:
        return target.as_posix()
