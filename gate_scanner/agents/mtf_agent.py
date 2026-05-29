"""
agents/mtf_agent.py
====================
Runs the analysis engines on each timeframe of each symbol and produces the
MTF summary used by the signal & ranking agents.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from .. import multi_timeframe as mtf_mod


class MTFAnalysisAgent:
    def analyze(self, mtf_data: Dict[str, pd.DataFrame], symbol: str = "") -> Dict:
        """
        Input:  { tf: DataFrame }
        Output: {
            "per_tf": { tf: { ema, structure, gate, breakout_prob } },
            "summary": mtf_summary(...)
        }

        BUG-1 / MISS-3 fix: symbol and timeframe are now passed into
        analyze_timeframe so the monthly blue-chip EMA exception and
        correction_age duration lookup work correctly.
        """
        per_tf = {
            tf: mtf_mod.analyze_timeframe(df, timeframe=tf, symbol=symbol)
            for tf, df in mtf_data.items()
        }
        summary = mtf_mod.mtf_summary(per_tf)
        return {"per_tf": per_tf, "summary": summary}
