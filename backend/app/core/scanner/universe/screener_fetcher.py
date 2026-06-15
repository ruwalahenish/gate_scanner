"""
screener_fetcher.py
===================
Fetches and parses company fundamental data from Screener.in.

Data sourced from static HTML on /company/{SYMBOL}/consolidated/:
  - Top-ratios section  → price, 52w H/L, P/E, P/B, ROCE, ROE, dividend yield, market cap
  - Profit-loss table   → OPM%, EPS, revenue/profit YoY growth and 3y CAGR
  - Balance-sheet table → debt-to-equity ratio
  - Cash-flow table     → free cash flow (operating + investing)
  - Ratios table        → debtor days (historical)
  - Shareholding table  → promoter/FII/DII holding %

Usage:
    from app.core.scanner.universe.screener_fetcher import fetch_company, strip_yf_suffix

    data = fetch_company("RELIANCE")     # bare symbol
    data = fetch_company("RELIANCE.NS")  # .NS suffix stripped automatically

Returns a dict of parsed fields or an empty dict on failure.
Rate limit is built in: 1.5–3.5s sleep between calls.
"""
from __future__ import annotations

import logging
import math
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.screener.in/company/{symbol}/consolidated/"
_MIN_DELAY = 1.5
_MAX_DELAY = 3.5
_RETRIES = 3
_TIMEOUT = 15

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.screener.in/",
})


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def strip_yf_suffix(symbol: str) -> str:
    """'RELIANCE.NS' → 'RELIANCE', '530965.BO' → '530965'."""
    for sfx in (".NS", ".BO", ".ns", ".bo"):
        if symbol.endswith(sfx):
            return symbol[: -len(sfx)]
    return symbol


# ---------------------------------------------------------------------------
# Internal: number parsing
# ---------------------------------------------------------------------------

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _parse_cell(text: str, is_pct_row: bool = False) -> Optional[float]:
    """
    Parse a Screener.in table cell value.

    Handles:
      "7.78 %"    → 0.0778  (fraction)
      "(1,23,456)" → -123456.0  (negative, Indian comma notation)
      "83,454"    → 83454.0
      "₹ 1,307"  → 1307.0
      ""  / "-"   → None

    is_pct_row: if True, treat plain numbers as percents → divide by 100.
    """
    if not text:
        return None
    text = text.strip()
    if text in ("-", "—", ""):
        return None

    # Detect percentage marker
    is_pct = "%" in text or is_pct_row

    # Strip currency symbol, whitespace, commas
    text = re.sub(r"[₹\s,]", "", text)
    text = text.replace("%", "")

    # Negative in parentheses: "(1234)" → "-1234"
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    # Strip "Cr" suffix (market cap in top-ratios comes as "17,67,773 Cr")
    text = text.rstrip("Cr").strip()

    v = _safe_float(text)
    if v is None:
        return None
    return v / 100.0 if is_pct else v


# ---------------------------------------------------------------------------
# Internal: HTTP fetch
# ---------------------------------------------------------------------------

def _fetch_page(symbol: str) -> Optional[BeautifulSoup]:
    """Fetch Screener.in consolidated page with retry on rate-limit responses."""
    url = _BASE_URL.format(symbol=symbol)
    for attempt in range(_RETRIES):
        try:
            resp = _SESSION.get(url, timeout=_TIMEOUT)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            if resp.status_code == 404:
                logger.debug("screener: %s not found (404)", symbol)
                return None
            if resp.status_code in (429, 503):
                wait = (2 ** attempt) * 3 + random.uniform(1, 4)
                logger.warning("screener: rate-limited (%s) for %s, retry in %.1fs",
                               resp.status_code, symbol, wait)
                time.sleep(wait)
                continue
            logger.warning("screener: unexpected HTTP %s for %s", resp.status_code, symbol)
            return None
        except requests.RequestException as exc:
            wait = (2 ** attempt) * 2 + random.uniform(1, 3)
            if attempt < _RETRIES - 1:
                logger.debug("screener: request failed for %s (%s), retry in %.1fs",
                             symbol, exc, wait)
                time.sleep(wait)
            else:
                logger.warning("screener: all retries exhausted for %s: %s", symbol, exc)
    return None


# ---------------------------------------------------------------------------
# Internal: section parsers
# ---------------------------------------------------------------------------

def _parse_top_ratios(soup: BeautifulSoup) -> dict:
    """
    Extract key ratios from the #top-ratios <ul> section.

    Returns partial result dict. Monetary values (price, market_cap, book_value)
    are in rupees / raw units. Percentage fields (roce, roe, dividend_yield) are
    stored as fractions (0.0778 = 7.78 %).
    """
    result: dict = {}
    section = soup.find(id="top-ratios")
    if not section:
        return result

    for li in section.find_all("li"):
        name_el = li.find("span", class_="name")
        value_el = li.find("span", class_="number")
        if not name_el or not value_el:
            continue
        name = name_el.get_text(" ", strip=True).lower()
        raw  = value_el.get_text(" ", strip=True)

        if "market cap" in name:
            # "₹ 17,67,773 Cr" → rupees
            v = _parse_cell(raw)
            if v is not None:
                result["market_cap"] = int(v * 10_000_000)   # Cr → rupees

        elif "current price" in name:
            # "₹ 1,307" → 1307.0
            v = _parse_cell(raw)
            result["screener_price"] = v

        elif "high / low" in name or ("high" in name and "low" in name):
            # "1,612 / 1,253"
            parts = re.sub(r"[₹\s,]", "", raw).split("/")
            if len(parts) == 2:
                result["screener_52w_high"] = _safe_float(parts[0])
                result["screener_52w_low"]  = _safe_float(parts[1])

        elif name.startswith("stock p/e") or name == "p/e":
            result["pe_ratio"] = _parse_cell(raw)

        elif "price to book" in name or name.startswith("p/b"):
            result["pb_ratio"] = _parse_cell(raw)

        elif "roce" in name:
            v = _parse_cell(raw, is_pct_row=True)   # "7.78 %" → 0.0778
            result["roce_actual"] = v

        elif name == "roe" or name.startswith("return on equity"):
            v = _parse_cell(raw, is_pct_row=True)
            result["roe"] = v

        elif "dividend yield" in name or "div. yield" in name:
            v = _parse_cell(raw, is_pct_row=True)
            result["dividend_yield"] = v

        elif "book value" in name:
            result["book_value"] = _parse_cell(raw)

    return result


def _parse_table_section(soup: BeautifulSoup, section_id: str) -> dict[str, list[float]]:
    """
    Parse a Screener.in data table section by its HTML id.

    Returns {row_label_lower: [val_oldest, ..., val_newest]}.
    Row labels with '+' toggle suffixes are stripped. Percentage rows auto-divide by 100.
    """
    section = soup.find(id=section_id)
    if not section:
        return {}

    table = section.find("table")
    if not table:
        return {}

    # Prefer tbody rows; fall back to all rows after the first
    tbody = table.find("tbody")
    rows: list[Tag] = list(tbody.find_all("tr")) if tbody else list(table.find_all("tr"))[1:]

    result: dict[str, list[float]] = {}
    for tr in rows:
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        # Label = first cell text, strip trailing '+' (Screener toggle) and whitespace
        label = cells[0].get_text(" ", strip=True).rstrip("+").strip().lower()
        if not label:
            continue

        is_pct_row = "%" in label or "opm" in label or "tax %" in label

        values: list[float] = []
        for cell in cells[1:]:
            raw = cell.get_text(strip=True)
            # Skip column-header-looking cells (e.g. "Mar 2024", "TTM")
            if re.match(r"^\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|ttm|\d{4})\s*$",
                        raw, re.I):
                continue
            v = _parse_cell(raw, is_pct_row=is_pct_row)
            if v is not None:
                values.append(v)

        if values:
            result[label] = values

    return result


def _get_latest(table: dict[str, list[float]], *labels: str) -> Optional[float]:
    """Return the most recent (rightmost) value for the first matching row label."""
    for label in labels:
        for key, values in table.items():
            if label.lower() in key:
                return values[-1] if values else None
    return None


def _yoy_growth(table: dict[str, list[float]], *labels: str) -> Optional[float]:
    """YoY growth = (last_year / year_before) - 1. Skips TTM column (uses [-2] and [-3])."""
    for label in labels:
        for key, values in table.items():
            if label.lower() in key and len(values) >= 3:
                # values[-1]=TTM, values[-2]=last FY, values[-3]=prev FY
                latest = values[-2]
                prev   = values[-3]
                if prev and prev != 0 and latest is not None:
                    return (latest / prev) - 1.0
    return None


def _cagr_3y(table: dict[str, list[float]], *labels: str) -> Optional[float]:
    """3-year CAGR = (values[-2] / values[-5])^(1/3) - 1 (uses annual FY data)."""
    for label in labels:
        for key, values in table.items():
            if label.lower() in key and len(values) >= 5:
                latest   = values[-2]   # last FY
                past     = values[-5]   # 3 FYs ago
                if past and past > 0 and latest and latest > 0:
                    return (latest / past) ** (1.0 / 3.0) - 1.0
    return None


def _parse_shareholding(soup: BeautifulSoup) -> dict:
    """Extract latest promoter, FII, DII holding percentages from the shareholding table."""
    result: dict = {}
    section = soup.find(id="shareholding")
    if not section:
        return result

    table = section.find("table")
    if not table:
        return result

    tbody = table.find("tbody")
    rows = list(tbody.find_all("tr")) if tbody else list(table.find_all("tr"))[1:]

    for tr in rows:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(" ", strip=True).lower()
        # Last cell = most recent quarter
        latest_text = cells[-1].get_text(strip=True)
        pct = _parse_cell(latest_text, is_pct_row=True)
        if pct is None:
            continue
        if "promoter" in label:
            result["promoter_holding"] = round(pct * 100, 2)   # store as % (65.3, not 0.653)
        elif "fii" in label or "foreign" in label:
            result["fii_holding"] = round(pct * 100, 2)
        elif "dii" in label or "domestic" in label:
            result["dii_holding"] = round(pct * 100, 2)

    return result


def _parse_price_change(soup: BeautifulSoup) -> Optional[float]:
    """Extract today's % change from the company header area."""
    # Look for a span near the price containing "%" and a sign
    for el in soup.find_all(string=re.compile(r"[+-]?\d+\.?\d*\s*%")):
        m = re.search(r"([+-]?\d+\.?\d*)\s*%", el)
        if m:
            v = _safe_float(m.group(1))
            if v is not None:
                return v / 100.0
    return None


# ---------------------------------------------------------------------------
# Public: main entry point
# ---------------------------------------------------------------------------

def fetch_company(symbol: str) -> dict:
    """
    Fetch and parse a Screener.in consolidated company page.

    Args:
        symbol: NSE/BSE symbol, with or without .NS/.BO suffix.

    Returns:
        Parsed data dict (may be partial). Empty dict on failure.
        Always sleeps 1.5–3.5s before returning to self-rate-limit.

    Field conventions match existing stock_master columns:
        roe, roce_actual    → fractions (0.18 = 18 %)
        profit_margin,
        opm_latest          → fractions (0.15 = 15 %)
        dividend_yield      → fraction
        debt_to_equity      → percent-style (45.3 = 0.45×), matching yfinance convention
        promoter/fii/dii    → plain percent (65.3 = 65.3 %)
        revenue_growth,
        profit_growth,
        revenue_cagr_3y,
        profit_cagr_3y      → fractions (0.12 = 12 %)
        market_cap          → integer rupees
        screener_price,
        screener_52w_high,
        screener_52w_low    → rupees (float)
        screener_price_change_pct → fraction
    """
    bare = strip_yf_suffix(symbol)
    result: dict = {}

    try:
        soup = _fetch_page(bare)
        if soup is None:
            return {}

        # 1. Key ratios (price, P/E, P/B, ROCE, ROE, market cap, dividend yield, book value)
        result.update(_parse_top_ratios(soup))

        # 2. Today's % change
        pct_chg = _parse_price_change(soup)
        if pct_chg is not None:
            result["screener_price_change_pct"] = pct_chg

        # 3. Profit-loss table
        pl = _parse_table_section(soup, "profit-loss")
        if pl:
            opm = _get_latest(pl, "opm %", "opm%", "opm")
            result["opm_latest"]      = opm              # already fraction (is_pct_row=True)
            result["profit_margin"]   = opm              # replaces yfinance profitMargins

            result["eps"]             = _get_latest(pl, "eps in rs", "eps")
            result["revenue_growth"]  = _yoy_growth(pl, "sales", "revenue")
            result["profit_growth"]   = _yoy_growth(pl, "net profit", "pat", "profit")
            result["revenue_cagr_3y"] = _cagr_3y(pl, "sales", "revenue")
            result["profit_cagr_3y"]  = _cagr_3y(pl, "net profit", "pat", "profit")

        # 4. Balance-sheet table → debt-to-equity
        bs = _parse_table_section(soup, "balance-sheet")
        if bs:
            borrowings = _get_latest(bs, "borrowings")
            equity_cap = _get_latest(bs, "equity capital", "share capital")
            reserves   = _get_latest(bs, "reserves")
            if borrowings is not None:
                total_equity = (equity_cap or 0) + (reserves or 0)
                if total_equity > 0:
                    # Percent-style to match yfinance convention (45.3 = 0.45×)
                    result["debt_to_equity"] = round((borrowings / total_equity) * 100.0, 2)

        # 5. Cash-flow table → free cash flow
        cf = _parse_table_section(soup, "cash-flow")
        if cf:
            op_cf  = _get_latest(cf, "cash from operating", "operating activity")
            inv_cf = _get_latest(cf, "cash from investing", "investing activity")
            fcf = _get_latest(cf, "free cash flow")
            if fcf is None and op_cf is not None and inv_cf is not None:
                fcf = op_cf + inv_cf   # approx FCF = operating + investing
            if fcf is not None:
                result["free_cash_flow"] = int(fcf * 10_000_000)   # Cr → rupees

        # 6. Ratios table → debtor days
        ratios = _parse_table_section(soup, "ratios")
        if ratios:
            dd = _get_latest(ratios, "debtor days", "debtors days")
            result["debtor_days"] = dd

        # 7. Shareholding
        result.update(_parse_shareholding(soup))

        # Remove None values so callers can use .get() cleanly
        result = {k: v for k, v in result.items() if v is not None}

        logger.debug("screener: parsed %d fields for %s", len(result), bare)

    except Exception as exc:
        logger.warning("screener: unexpected error for %s: %s", bare, exc)
        result = {}

    finally:
        # Self-rate-limit regardless of success/failure
        time.sleep(_MIN_DELAY + random.uniform(0, _MAX_DELAY - _MIN_DELAY))

    return result
