from pydantic import BaseModel, UUID4
from datetime import datetime
from typing import Optional


class ScanStatus(BaseModel):
    id: UUID4
    triggered_at: datetime
    completed_at: Optional[datetime] = None
    mode: str
    status: str
    universe_size: Optional[int] = None
    passed_filter: Optional[int] = None
    signals_found: Optional[int] = None
    duration_sec: Optional[float] = None
    error_message: Optional[str] = None


class TriggerScanRequest(BaseModel):
    mode: str = "daily"          # daily | full | fno | custom
    universe: list[str] = []     # empty = use default universe for mode


class TriggerScanResponse(BaseModel):
    scan_id: str
    status: str = "pending"
