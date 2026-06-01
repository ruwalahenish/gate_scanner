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
# Phase 3 — yfinance fundamentals enrichment
# ---------------------------------------------------------------------------

def phase3_enrich_fundamentals(
    pending_rows: list[dict],
    batch_size: int = 10,
    delay_between_batches: float = 2.0,
) -> list[dict]:
    """
    Fetch yfinance .info for each symbol in the pending list.

    yfinance symbol format:
        NSE → '{symbol}.NS'
        BSE → symbol already contains '.BO' (convention from nse_universe.py)

    Fields extracted from ticker.info:
        sector, industry, marketCap, trailingPE, priceToBook,
        dividendYield, trailingEps, bookValue

    Returns list of result dicts, one per input row, with keys:
        symbol, exchange, sector, industry, market_cap, pe_ratio,
        pb_ratio, dividend_yield, eps, book_value, success, error
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed — cannot enrich fundamentals")
        return [
            {**row, "success": False, "error": "yfinance not installed",
             "sector": None, "industry": None, "market_cap": None,
             "pe_ratio": None, "pb_ratio": None, "dividend_yield": None,
             "eps": None, "book_value": None}
            for row in pending_rows
        ]

    results: list[dict] = []
    total = len(pending_rows)

    for i, row in enumerate(pending_rows):
        symbol   = row["symbol"]
        exchange = row.get("exchange", "NSE")

        # Build yfinance ticker symbol
        if exchange == "BSE" or symbol.endswith(".BO"):
            yf_sym = symbol if symbol.endswith(".BO") else f"{symbol}.BO"
        else:
            yf_sym = f"{symbol}.NS"

        result: dict = {
            "symbol": symbol, "exchange": exchange,
            "sector": None, "industry": None, "market_cap": None,
            "pe_ratio": None, "pb_ratio": None, "dividend_yield": None,
            "eps": None, "book_value": None,
            "success": False, "error": None,
        }

        try:
            info = yf.Ticker(yf_sym).info
            result.update({
                "sector":         info.get("sector"),
                "industry":       info.get("industry"),
                "market_cap":     _safe_int(info.get("marketCap")),
                "pe_ratio":       _safe_float(info.get("trailingPE")),
                "pb_ratio":       _safe_float(info.get("priceToBook")),
                "dividend_yield": _safe_float(info.get("dividendYield")),
                "eps":            _safe_float(info.get("trailingEps")),
                "book_value":     _safe_float(info.get("bookValue")),
                "success":        True,
            })
        except Exception as e:
            result["error"] = str(e)[:300]
            logger.debug("yfinance failed for %s: %s", yf_sym, e)

        results.append(result)

        # Rate-limit: sleep after each batch
        if (i + 1) % batch_size == 0 and (i + 1) < total:
            time.sleep(delay_between_batches)

    succeeded = sum(1 for r in results if r["success"])
    logger.info(
        "Phase 3: enriched %d/%d symbols (failed: %d)",
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
        f = float(v)
        return None if (f != f) else f   # NaN check
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
