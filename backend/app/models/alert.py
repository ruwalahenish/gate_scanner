from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional


ALERT_TYPES = {
    "price_above", "price_below",
    "gate_score_gte", "gate_score_lte",
    "volume_spike", "category_upgrade",
    "breakout_detected", "sl_breach_warning", "target_proximity",
}


class CreateAlertRequest(BaseModel):
    symbol: str
    alert_type: str
    threshold_value: Optional[float] = None
    timeframe: Optional[str] = None
    message: Optional[str] = None
    notify_via: list[str] = ["web"]


class AlertModel(BaseModel):
    id: UUID4
    symbol: str
    alert_type: str
    status: str
    threshold_value: Optional[float] = None
    timeframe: Optional[str] = None
    message: Optional[str] = None
    notify_via: list[str]
    triggered_at: Optional[datetime] = None
    triggered_price: Optional[float] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
