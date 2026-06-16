"""
stock_master_sync.py
====================
Three-phase synchronous sync engine for the stock_master table.

Phase 1: NSE EQUITY_L.csv  → fetch all ~1900 EQ-series stocks with full metadata
Phase 2: NSE Index CSVs    → fetch all 6 Nifty index constituent lists concurrently
Phase 3: yfinance .info    → enrich pending/failed rows with fundamentals

All phases are independently resumable:
  - Phases 1 & 2 use ON CONFLICT upsert — safe to re-run
  - Phase 3 processes only rows with sync_status IN ('pending', 'failed')

This module is pure synchronous I/O — it runs in a ThreadPoolExecutor
from stock_service.py, exactly as scan_service.py wraps pipeline.run_scan().
"""
from __future__ import annotations

import logging
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
}

EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

INDEX_URLS: dict[str, str] = {
    "nifty50":      "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "nifty_next50": "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv",
    "nifty100":     "https://archives.nseindia.com/content/indices/ind_nifty100list.csv",
    "nifty500":     "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "midcap150":    "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "smallcap100":  "https://archives.nseindia.com/content/indices/ind_niftysmallcap100list.csv",
}

# ---------------------------------------------------------------------------
# Phase 1 — NSE EQUITY_L.csv
# ---------------------------------------------------------------------------

def phase1_fetch_nse_equity() -> list[dict]:
    """
    Download EQUITY_L.csv from NSE and extract all EQ-series stocks with
    full metadata (company name, ISIN, series, listing date, face value,
    market lot).

    CSV columns (0-indexed):
        0  SYMBOL
        1  NAME OF COMPANY
        2  SERIES
        3  DATE OF LISTING   (DD-MMM-YYYY)
        4  PAID UP VALUE      (face value in ₹)
        5  MARKET LOT
        6  ISIN NUMBER
        7  FACE VALUE

    Returns list of dicts with keys matching stock_master columns.
    Raises on network error — caller catches and logs.
    """
    req = urllib.request.Request(EQUITY_URL, headers=_NSE_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")

    rows: list[dict] = []
    lines = raw.splitlines()
    if not lines:
        raise ValueError("EQUITY_L.csv returned empty content")

    for line in lines[1:]:   # skip header
        parts = line.split(",")
        if len(parts) < 7:
            continue

        symbol  = parts[0].strip().strip('"')
        name    = parts[1].strip().strip('"')
        series  = parts[2].strip().strip('"')

        if not symbol or series != "EQ":
            continue

        # DATE OF LISTING — format varies: "14-JUN-1995" or empty
        listing_date = None
        raw_date = parts[3].strip().strip('"')
        if raw_date:
            for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
                try:
                    listing_date = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    pass

        face_value = _parse_float(parts[4])
        market_lot = _parse_int(parts[5])
        isin       = parts[6].strip().strip('"') or None

        rows.append({
            "symbol":       symbol,
            "exchange":     "NSE",
            "company_name": name or symbol,
            "isin":         isin,
            "series":       series,
            "face_value":   face_value,
            "listing_date": listing_date,
            "market_lot":   market_lot,
        })

    if len(rows) < 500:
        raise ValueError(
            f"EQUITY_L.csv returned only {len(rows)} EQ rows — format may have changed"
        )

    logger.info("Phase 1: fetched %d NSE EQ-series stocks from EQUITY_L.csv", len(rows))
    return rows


# ---------------------------------------------------------------------------
# Phase 2 — NSE Index CSVs
# ---------------------------------------------------------------------------

def phase2_fetch_index_memberships() -> dict[str, set[str]]:
    """
    Download all 6 Nifty index CSVs concurrently and return constituent sets.

    Each CSV has columns: Company Name, Industry, Symbol, Series, ISIN Code
    (Symbol is at index 2, 0-based).

    Partial failures are tolerated — the missing index will simply not be
    updated this run, preserving existing flags.

    Returns: {'nifty50': {'RELIANCE', 'TCS', ...}, 'nifty500': {...}, ...}
    """
    results: dict[str, set[str]] = {}

    def _fetch_one(name: str, url: str) -> tuple[str, set[str] | None]:
        try:
            req = urllib.request.Request(url, headers=_NSE_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            symbols: set[str] = set()
            for line in raw.splitlines()[1:]:
                parts = line.split(",")
                if len(parts) >= 3:
                    sym = parts[2].strip().strip('"')
                    if sym:
                        symbols.add(sym)
            if len(symbols) < 10:
                logger.warning("Index %s returned only %d symbols", name, len(symbols))
                return name, None
            return name, symbols
        except Exception as e:
            logger.warning("Failed to fetch index %s: %s", name, e)
            return name, None

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_fetch_one, name, url): name for name, url in INDEX_URLS.items()}
        for fut in as_completed(futures):
            name, symbols = fut.result()
            if symbols is not None:
                results[name] = symbols
                logger.info("Phase 2: %s — %d constituents", name, len(symbols))

    return results


# ---------------------------------------------------------------------------
# Phase 2b — BSE equity master (ListofScripData API)
# ---------------------------------------------------------------------------

_BSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bseindia.com/markets/equity/EQReports/MarketWatch.aspx",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.bseindia.com",
}

_BSE_SCRIP_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"

# BSE board groups to ingest. A/B are the actively-traded equity boards that
# cover every meaningful BSE-only company. The illiquid penny boards (X, XT, Z,
# T, etc.) are intentionally skipped — they would add thousands of near-dead
# scrips that only inflate scan time and get dropped by the liquidity prefilter.
_BSE_GROUPS = ("A", "B")


def _bse_field(item: dict, *names: str) -> str | None:
    """Return the first present, non-empty value among several candidate keys."""
    for n in names:
        if n in item and item[n] is not None:
            v = item[n]
            v = str(int(v)) if isinstance(v, (int, float)) else str(v).strip()
            if v:
                return v
    return None


def phase_bse_fetch_equity(groups: tuple[str, ...] = _BSE_GROUPS) -> list[dict]:
    """
    Download the BSE equity scrip master and return one dict per active scrip.

    yfinance addresses BSE stocks by their *numeric scrip code* + ".BO"
    (e.g. RELIANCE on BSE → "500325.BO"); the alpha ticker does not resolve.
    We therefore store the numeric scrip code as `symbol` and exchange="BSE";
    get_master_universe() appends ".BO" downstream.

    Dual-listed (NSE+BSE) stocks are NOT removed here — the caller dedupes by
    ISIN against the NSE rows already in stock_master, which is the only
    reliable key (numeric BSE codes never equal alpha NSE symbols).

    Returns a list of dicts shaped for upsert_stocks_batch(); [] on failure.
    """
    import json
    import urllib.request

    seen: dict[str, dict] = {}   # scrip_cd -> row (dedupe across groups)

    for group in groups:
        try:
            url = (
                f"{_BSE_SCRIP_URL}?Group={group}&Exportflag=1"
                "&indexname=&scripname=&strsearch="
            )
            req = urllib.request.Request(url, headers=_BSE_HEADERS)
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            items = (
                data if isinstance(data, list)
                else (data.get("Table") or data.get("Table1") or data.get("data") or [])
            )

            for item in items:
                if not isinstance(item, dict):
                    continue
                scrip_cd = _bse_field(item, "SCRIP_CD", "scrip_cd", "Scrip_Cd")
                # Must be a numeric scrip code to be a valid yfinance .BO ticker
                if not scrip_cd or not scrip_cd.isdigit():
                    continue

                name = _bse_field(
                    item, "Scrip_Name", "scrip_name", "SCRIP_NAME",
                    "Company_Name", "company_name", "ISSUER_NAME",
                ) or scrip_cd
                isin = _bse_field(item, "ISIN_NUMBER", "ISIN", "Isin_Number", "isin")
                face = _bse_field(item, "FACE_VALUE", "Face_Value", "face_value")

                try:
                    face_value = float(face) if face else None
                except ValueError:
                    face_value = None

                seen[scrip_cd] = {
                    "symbol":       scrip_cd,
                    "exchange":     "BSE",
                    "company_name": name[:200],
                    "isin":         (isin[:12] if isin else None),
                    "series":       group,        # store BSE board group
                    "face_value":   face_value,
                    "listing_date": None,
                    "market_lot":   None,
                }
        except Exception as e:
            logger.warning("BSE group %s fetch failed: %s", group, e)

    rows = list(seen.values())
    if len(rows) < 50:
        logger.warning(
            "BSE scrip master returned only %d rows — API may have changed format",
            len(rows),
        )
        return []

    logger.info("Phase BSE: fetched %d BSE scrips from groups %s", len(rows), ",".join(groups))
    return rows


# ---------------------------------------------------------------------------
# Phase 3 — fundamentals enrichment (Screener.in only)
# ---------------------------------------------------------------------------

def phase3_enrich_fundamentals(
    pending_rows: list[dict],
    batch_size: int = 10,
    delay_between_batches: float = 2.0,
) -> list[dict]:
    """
    Enrich fundamentals for each pending symbol via Screener.in.

    yfinance is NOT used for fundamentals — only for OHLCV and live price.
    If Screener.in returns empty for a symbol the row is marked failed so
    it can be retried on the next scheduled run.

    Result dict keys (per input row):
        symbol, exchange, market_cap, pe_ratio, pb_ratio, dividend_yield,
        eps, book_value, roe, roce_actual, revenue_growth, profit_growth,
        debt_to_equity, profit_margin, opm_latest, free_cash_flow,
        promoter_holding, fii_holding, dii_holding, debtor_days,
        revenue_cagr_3y, profit_cagr_3y, screener_price, screener_52w_high,
        screener_52w_low, screener_price_change_pct, data_source,
        success, error
    """
    from app.core.scanner.universe.screener_fetcher import fetch_company

    _empty_fundamentals: dict = {
        "sector": None, "industry": None, "market_cap": None,
        "pe_ratio": None, "pb_ratio": None, "dividend_yield": None,
        "eps": None, "book_value": None,
        "roe": None, "roce": None, "revenue_growth": None,
        "profit_growth": None, "debt_to_equity": None, "profit_margin": None,
        "roce_actual": None, "opm_latest": None, "free_cash_flow": None,
        "promoter_holding": None, "fii_holding": None, "dii_holding": None,
        "debtor_days": None, "revenue_cagr_3y": None, "profit_cagr_3y": None,
        "screener_price": None, "screener_52w_high": None,
        "screener_52w_low": None, "screener_price_change_pct": None,
        "data_source": "screener",
    }

    results: list[dict] = []
    total = len(pending_rows)

    for i, row in enumerate(pending_rows):
        symbol   = row["symbol"]
        exchange = row.get("exchange", "NSE")

        result: dict = {
            "symbol": symbol, "exchange": exchange,
            **_empty_fundamentals,
            "success": False, "error": None,
        }

        try:
            data = fetch_company(symbol)   # rate-limit sleep (1.5–3.5 s) built-in
            if data:
                result.update(data)
                result["data_source"] = "screener"
                result["success"] = True
            else:
                result["error"] = "screener_fetcher returned empty result"
                logger.debug("screener: no data for %s (%s)", symbol, exchange)
        except Exception as exc:
            result["error"] = str(exc)[:300]
            logger.debug("screener: exception for %s: %s", symbol, exc)

        results.append(result)
        if (i + 1) % batch_size == 0 and (i + 1) < total:
            time.sleep(delay_between_batches)

    succeeded = sum(1 for r in results if r["success"])
    logger.info(
        "Phase 3: enriched %d/%d symbols via Screener.in (failed=%d)",
        succeeded, total, total - succeeded,
    )
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_float(s: str) -> float | None:
    s = s.strip().strip('"')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(s: str) -> int | None:
    s = s.strip().strip('"')
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        import math
        f = float(v)
        return None if (not math.isfinite(f)) else f   # reject NaN and ±inf
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
