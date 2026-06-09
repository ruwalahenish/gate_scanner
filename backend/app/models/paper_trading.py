from pydantic import BaseModel, UUID4, field_validator
from datetime import datetime
from typing import Optional


class SellRequest(BaseModel):
    position_id: str
    quantity: int
    price: float
    exit_reason: str = "manual"
    notes: Optional[str] = None

    @field_validator("exit_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        allowed = {"manual", "sl_hit", "t1_hit", "t2_hit", "t3_hit", "trail"}
        if v not in allowed:
            raise ValueError(f"exit_reason must be one of {allowed}")
        return v


class PositionModel(BaseModel):
    id: UUID4
    symbol: str
    side: str
    quantity: int
    avg_entry: float
    stop_loss: Optional[float] = None
    t1: Optional[float] = None
    t2: Optional[float] = None
    t3: Optional[float] = None
    trailing_sl: Optional[float] = None
    current_sl_level: str
    signal_id: Optional[UUID4] = None
    opened_at: datetime
    status: str
    notes: Optional[str] = None
    auto_created: bool = False
    creation_source: str = "manual"
    # Computed at query time
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None


class TradeModel(BaseModel):
    id: UUID4
    position_id: Optional[UUID4] = None
    symbol: str
    side: str
    quantity: int
    price: float
    executed_at: datetime
    exit_reason: Optional[str] = None
    pnl_abs: Optional[float] = None
    pnl_pct: Optional[float] = None
    notes: Optional[str] = None


class PaperTradingSummary(BaseModel):
    initial_capital: float
    current_capital: float
    invested_value: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    total_pnl_pct: float
    open_positions: int
    total_trades: int
    winning_trades: int
    win_rate: float
