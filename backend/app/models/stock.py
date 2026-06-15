from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class StockSearchResult(BaseModel):
    """Compact shape for search autocomplete and universe lookups."""
    symbol: str
    exchange: str
    company_name: str
    isin: Optional[str] = None
    sector: Optional[str] = None
    in_nifty50: bool = False
    in_nifty500: bool = False
    market_cap: Optional[int] = None


class StockResponse(StockSearchResult):
    """Full detail view returned by GET /api/stocks/{symbol}."""
    series: Optional[str] = None
    face_value: Optional[float] = None
    listing_date: Optional[date] = None
    market_lot: Optional[int] = None
    in_nifty_next50: bool = False
    in_nifty100: bool = False
    in_midcap150: bool = False
    in_smallcap100: bool = False
    is_fno: bool = False
    industry: Optional[str] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    eps: Optional[float] = None
    book_value: Optional[float] = None
    sync_status: str = "pending"
    last_synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    data_source: Optional[str] = None
    # Extended Screener.in fundamentals
    roce_actual: Optional[float] = None
    opm_latest: Optional[float] = None
    free_cash_flow: Optional[int] = None
    promoter_holding: Optional[float] = None
    fii_holding: Optional[float] = None
    dii_holding: Optional[float] = None
    debtor_days: Optional[float] = None
    revenue_cagr_3y: Optional[float] = None
    profit_cagr_3y: Optional[float] = None
    # Screener.in EOD price (post-market display reference)
    screener_price: Optional[float] = None
    screener_52w_high: Optional[float] = None
    screener_52w_low: Optional[float] = None
    screener_price_change_pct: Optional[float] = None
    screener_price_updated_at: Optional[datetime] = None
    # Latest scan signal data (null if stock has never appeared in a scan result)
    latest_category: Optional[str] = None
    latest_rank_score: Optional[float] = None
    latest_gate_strength: Optional[float] = None
    latest_confidence: Optional[float] = None
    latest_side: Optional[str] = None
    latest_signal_timeframe: Optional[str] = None
    latest_entry: Optional[float] = None
    latest_stop_loss: Optional[float] = None
    latest_t1: Optional[float] = None
    latest_rr_t1: Optional[float] = None
    # Live price (fetched inline by list endpoint, not stored in DB)
    live_price: Optional[float] = None


class StockListResponse(BaseModel):
    total: int
    items: list[StockResponse]


class SyncTriggerRequest(BaseModel):
    phases: list[str] = ["equity", "bse_equity", "index_flags", "fundamentals"]


class SyncTriggerResponse(BaseModel):
    task_id: str
    phases: list[str]
    status: str
