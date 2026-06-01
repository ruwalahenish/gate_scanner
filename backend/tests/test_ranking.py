"""
Unit tests for the GATE ranking and classification engines.
These are pure-function tests — no DB, no network.
"""
def _make_signal(gate=70.0, alignment=80.0, structure=75.0, breakout=65.0, rr_t2=3.0):
    return {
        "gate_strength": gate,
        "mtf_alignment_pct": alignment,
        "structure_quality": structure,
        "breakout_probability": breakout,
        "rr": {"T1": 1.8, "T2": rr_t2, "T3": 4.5},
        "htf_confirmed": True,
        "entry": 100.0,
        "stop_loss": 92.0,
        "T1": 108.0, "T2": 115.0, "T3": 125.0,
        "rank_score": 0.0,
    }


def test_composite_score_range():
    from app.core.ranking.ranking_engine import composite_score
    signal = _make_signal()
    score = composite_score(signal)
    assert 0 <= score <= 100, f"Score out of range: {score}"


def test_htf_boost_increases_score():
    from app.core.ranking.ranking_engine import composite_score
    base = _make_signal()
    boosted = {**base, "htf_confirmed": True}
    unboosted = {**base, "htf_confirmed": False}
    assert composite_score(boosted) > composite_score(unboosted)


def test_high_gate_score_produces_high_rank():
    from app.core.ranking.ranking_engine import composite_score
    strong = _make_signal(gate=95, alignment=95, structure=90, breakout=90)
    weak = _make_signal(gate=30, alignment=30, structure=25, breakout=20)
    assert composite_score(strong) > composite_score(weak)


def test_rank_scores_are_sorted_descending():
    from app.core.ranking.ranking_engine import rank
    signals = [
        _make_signal(gate=50),
        _make_signal(gate=90),
        _make_signal(gate=70),
    ]
    ranked = rank(signals)
    scores = [s["rank_score"] for s in ranked]
    assert scores == sorted(scores, reverse=True)
