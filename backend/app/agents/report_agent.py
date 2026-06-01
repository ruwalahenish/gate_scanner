"""
agents/report_agent.py
=======================
Final-output agent — prints to console and writes CSV/JSON/HTML dumps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from app.agents.base import BaseAgent
from app.core.reporting import reporting
from app.core.reporting import charting
from app.core.reporting.scan_report import build_scan_report


class ReportGenerationAgent(BaseAgent):
    def __init__(self, out_dir: str = "./gate_output"):
        super().__init__()
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(exist_ok=True, parents=True)

    def render(
        self,
        results: List[Dict],
        detail_symbols: Optional[List[str]] = None,
        scan_meta: Optional[Dict] = None,
    ):
        # Console summary
        reporting.print_summary(results)

        # Determine which symbols get detail panels (and charts)
        if detail_symbols:
            detail_results = [r for r in results if r["symbol"] in detail_symbols]
        else:
            # Auto: top 3 of INVESTMENT/SWING that have signals
            detail_results = []
            for r in results:
                if r["classification"]["category"] in ("INVESTMENT", "SWING") and r.get("signal"):
                    detail_results.append(r)
                if len(detail_results) >= 3:
                    break

        charts_dir = self.out_dir / "charts"
        for r in detail_results:
            reporting.detail_panel(r)
            # Generate candlestick chart if signal and OHLCV data are available
            sig  = r.get("signal")
            ohlcv = r.get("ohlcv")
            if sig and ohlcv:
                tf = sig.get("signal_timeframe", "1d")
                df = ohlcv.get(tf)
                if df is not None and not df.empty:
                    chart_path = str(charts_dir / f"{r['symbol']}_{tf}.html")
                    saved = charting.build_signal_chart(r["symbol"], df, sig, chart_path)
                    if saved:
                        print(f"  Chart → {saved}")

        # File dumps
        csv_path  = self.out_dir / "signals.csv"
        json_path = self.out_dir / "signals.json"
        reporting.write_csv(results, str(csv_path))
        # Strip heavy nested data from JSON to keep it readable
        slim = []
        for r in results:
            slim.append({
                "symbol":         r["symbol"],
                "classification": r["classification"],
                "signal":         r.get("signal"),
                "mtf_summary":    r.get("mtf_summary"),
            })
        reporting.write_json(slim, str(json_path))

        # HTML report
        html_path = build_scan_report(
            results,
            out_dir=self.out_dir,
            charts_dir=charts_dir,
            scan_meta=scan_meta or {},
        )
        print(f"  HTML Report → {html_path}")

        return {"csv": str(csv_path), "json": str(json_path), "html": html_path}
