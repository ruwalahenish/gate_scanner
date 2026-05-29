"""
agents/ranking_agent.py
========================
Composite ranking + classification across all signaled symbols.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .. import ranking_engine
from .. import classifier


class SignalRankingAgent:
    def rank_and_classify(self, scored_universe: List[Dict]) -> List[Dict]:
        """
        Input: list of dicts:
          {
            "symbol": str,
            "signal": Optional[dict],
            "mtf_per_tf": dict,
            "mtf_summary": dict,
          }
        Output: same list, with `signal.rank_score` set and `classification` attached,
        sorted by category priority and then rank_score desc.
        """
        # 1) Rank only those with signals
        with_signals    = [r for r in scored_universe if r.get("signal")]
        without_signals = [r for r in scored_universe if not r.get("signal")]

        ranked = ranking_engine.rank([r["signal"] for r in with_signals])
        # Map back rank_score onto each entry
        score_by_symbol = {s["symbol"]: s["rank_score"] for s in ranked}
        for r in with_signals:
            r["signal"]["rank_score"] = score_by_symbol.get(r["symbol"], 0.0)

        # 2) Classify everything
        for r in scored_universe:
            r["classification"] = classifier.classify(
                r["symbol"],
                r["mtf_per_tf"],
                r["mtf_summary"],
                r.get("signal"),
            )

        # 3) Sort: category priority then rank_score
        order = {"INVESTMENT": 0, "SWING": 1, "POSITIONAL": 2, "WATCH": 3, "IGNORE": 4}
        scored_universe.sort(
            key=lambda r: (
                order.get(r["classification"]["category"], 99),
                -((r.get("signal") or {}).get("rank_score", 0.0)),
            )
        )
        return scored_universe
