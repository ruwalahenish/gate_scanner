from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Literal, Optional


class SignalModel(BaseModel):
    id: UUID4
    scan_id: UUID4
    symbol: str
    category: str
    # User-facing labels (populated by router layer, not stored in DB)
    display_status: Optional[Literal["BUY", "BREAKOUT", "WATCH", "NO_ACTION"]] = None
    display_category: Optional[str] = None  # "Long-Term Buy", "Swing Buy", etc.
    side: Optional[str] = None
    signal_timeframe: Optional[str] = None
    sl_timeframe: Optional[str] = None
    trend_direction: Optional[str] = None
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    sl_distance_pct: Optional[float] = None
    t1: Optional[float] = None
    t2: Optional[float] = None
    t3: Optional[float] = None
    rr_t1: Optional[float] = None
    rr_t2: Optional[float] = None
    rr_t3: Optional[float] = None
    gate_strength: Optional[float] = None
    volatility_compression: Optional[float] = None
    breakout_probability: Optional[float] = None
    confidence: Optional[float] = None
    rank_score: Optional[float] = None
    mtf_alignment_pct: Optional[float] = None
    structure_quality: Optional[float] = None
    atr: Optional[float] = None
    htf_confirmed: Optional[bool] = None
    correction_validated: Optional[bool] = None
    bounce_sequence_valid: Optional[bool] = None
    fib_confluence: Optional[bool] = None
    phase: Optional[str] = None
    trailing_plan: Optional[dict] = None
    reasoning: Optional[str] = None
    # ---- strategy-rework fields (migration 008) ----
    breakout_state: Optional[str] = None
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    breakout_level: Optional[float] = None
    measured_move: Optional[float] = None
    rs_score: Optional[float] = None
    sector_momentum: Optional[float] = None
    accumulation_score: Optional[float] = None
    fundamental_score: Optional[float] = None
    volume_buildup: Optional[bool] = None
    created_at: datetime


class SignalFilters(BaseModel):
    category: Optional[str] = None
    min_rank: float = 0
    min_gate: float = 0
    side: Optional[str] = None
    timeframe: Optional[str] = None
    limit: int = 50
    offset: int = 0


class SignalListResponse(BaseModel):
    total: int
    items: list[SignalModel]
