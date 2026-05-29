"""
agents/risk_agent.py
=====================
Builds the actual trade signal (entry/SL/targets/RR) and enforces risk filters.

Wraps `signal_engine.generate_signal` but adds:
  * SL distance validation
  * RR floor check
  * "trailing SL" suggestion based on T2 hit
"""

from __future__ import annotations

from typing import Dict, Optional

from .. import config
from .. import signal_engine


class RiskManagementAgent:
    def __init__(self, min_rr: float = config.MIN_RR_RATIO,
                 max_sl_pct: float = config.MAX_SL_DISTANCE_PCT):
        self.min_rr = min_rr
        self.max_sl_pct = max_sl_pct

    def build_signal(
        self,
        symbol: str,
        mtf_data: Dict,
        mtf_per_tf: Dict,
        mtf_summary: Dict,
    ) -> Optional[Dict]:
        sig = signal_engine.generate_signal(symbol, mtf_data, mtf_per_tf, mtf_summary)
        if not sig:
            return None
        # Defensive checks (signal_engine already enforces, but double-check)
        if sig["rr"]["T1"] < self.min_rr:
            return None
        if sig["sl_distance_pct"] / 100 > self.max_sl_pct:
            return None
        # Suggest trailing SL: after T1 hit -> move SL to entry (BE); after T2 -> trail to T1
        sig["trailing_plan"] = {
            "on_T1_hit": "Move SL to entry (break-even).",
            "on_T2_hit": f"Trail SL to T1 ({sig['T1']:.2f}).",
            "on_T3_hit": "Exit or trail using prior swing on signal TF.",
        }
        return sig
