"""
nse_universe.py
================
Full Indian stock market universe:
  - Nifty 50, Nifty Next 50, Nifty Midcap 150, Nifty Smallcap 100
  - NSE F&O stocks (~200)
  - Key sectoral index constituents
  - BSE 100 additional (non-overlapping with NSE lists)

All symbols use the NSE ticker (no .NS suffix — data_fetcher adds it).
Total covered: ~700 unique symbols.

Data source for universe lists:
  Primary:   NSE India (nseindia.com) — CSV download of index constituents
  Fallback:  Maintained static list below (updated periodically)

To refresh the live universe, call get_full_universe(live=True) which fetches
the current Nifty 500 CSV from NSE India.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Universe disk-cache helpers (24 h TTL — same dir as OHLCV cache)
# ---------------------------------------------------------------------------

_UNIV_CACHE_HOURS = 24


def _univ_cache_dir() -> Path:
    d = Path(os.environ.get("GATE_CACHE_DIR", "./.gate_cache"))
    d.mkdir(exist_ok=True)
    return d


def _read_univ_cache(name: str) -> Optional[List[str]]:
    p = _univ_cache_dir() / f"_univ_{name}.txt"
    if p.exists() and (time.time() - p.stat().st_mtime) < _UNIV_CACHE_HOURS * 3600:
        syms = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        if syms:
            return syms
    return None


def _write_univ_cache(name: str, symbols: List[str]) -> None:
    try:
        (_univ_cache_dir() / f"_univ_{name}.txt").write_text(
            "\n".join(symbols), encoding="utf-8"
        )
    except Exception:
        pass

# ---------------------------------------------------------------------------
# NSE Index Constituents
# ---------------------------------------------------------------------------

NIFTY_50: List[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC",
    "LT", "SBIN", "KOTAKBANK", "AXISBANK", "HINDUNILVR", "BAJFINANCE",
    "MARUTI", "ASIANPAINT", "HCLTECH", "SUNPHARMA", "TITAN", "ULTRACEMCO",
    "WIPRO", "NTPC", "ONGC", "M&M", "POWERGRID", "NESTLEIND", "TATAMOTORS",
    "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV",
    "GRASIM", "HINDALCO", "DRREDDY", "CIPLA", "TECHM", "INDUSINDBK",
    "EICHERMOT", "BRITANNIA", "BPCL", "DIVISLAB", "HEROMOTOCO", "APOLLOHOSP",
    "TATACONSUM", "UPL", "BAJAJ-AUTO", "SBILIFE", "HDFCLIFE", "LTIM",
]

NIFTY_NEXT_50: List[str] = [
    "ADANIGREEN", "ADANITRANS", "AMBUJACEM", "AUROPHARMA", "BANDHANBNK",
    "BANKBARODA", "BEL", "BERGEPAINT", "BIOCON", "BOSCHLTD",
    "CANBK", "CHOLAFIN", "COLPAL", "DABUR", "DMART",
    "DLF", "GAIL", "GODREJCP", "HAVELLS", "ICICIGI",
    "ICICIPRULI", "INDUSTOWER", "LICI", "LUPIN", "MCDOWELL-N",
    "MUTHOOTFIN", "NAUKRI", "NYKAA", "OFSS", "PAGEIND",
    "PAYTM", "PETRONET", "PIDILITIND", "PNB", "RECLTD",
    "SAIL", "SHREECEM", "SIEMENS", "SRF", "TATACOMM",
    "TRENT", "TVSMOTOR", "VEDL", "VOLTAS", "ZOMATO",
    "LTTS", "MFSL", "PERSISTENT", "COFORGE", "INDHOTEL",
]

NIFTY_MIDCAP_150: List[str] = [
    "AARTIIND", "ABCAPITAL", "ABFRL", "ACC", "AIAENG",
    "AJANTPHARM", "ALKEM", "APLLTD", "ASTRAL", "ATUL",
    "AUBANK", "AWHCL", "BAJAJHLDNG", "BALRAMCHIN", "BATAINDIA",
    "BHARATFORG", "BHDL", "BLUESTARCO", "CAMS", "CANFINHOME",
    "CARBORUNIV", "CASTROLIND", "CEATLTD", "CENTURYPLY", "CGPOWER",
    "CMSINFO", "CONCOR", "CROMPTON", "CUMMINSIND", "CYIENT",
    "DALBHARAT", "DEEPAKNTR", "DELTACORP", "DIXON", "EIDPARRY",
    "ELGIEQUIP", "ENGINERSIN", "ESCORTS", "EXIDEIND", "FEDERALBNK",
    "FORTIS", "GLENMARK", "GLAXO", "GNFC", "GODREJIND",
    "GODREJPROP", "GRANULES", "GRAPHITE", "GREAVESCOT", "GSPL",
    "GUJGASLTD", "HAPPSTMNDS", "HFCL", "HINDPETRO", "HONAUT",
    "HUDCO", "IDBI", "IDFCFIRSTB", "IFCI", "IGL",
    "INDIAMART", "INDIANB", "IOC", "IRCTC", "ISEC",
    "JBCHEPHARM", "JINDALSAW", "JKTYRE", "JUBLFOOD", "JUBL",
    "KALPATPOWR", "KALYANKJIL", "KANSAINER", "KEI", "KPITTECH",
    "KRBL", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN", "M&MFIN",
    "MAHINDCIE", "MANAPPURAM", "MARICO", "MASTEK", "MCX",
    "MEDANTA", "METROPOLIS", "MFSL", "MIDHANI", "MINDTREE",
    "MOTILALOFS", "MRF", "MUTHOOTFIN", "NATCOPHARM", "NAUKRI",
    "NBCC", "NESCO", "NHPC", "NLCINDIA", "NMDC",
    "NOCIL", "NUVOCO", "OBEROIRLTY", "OIL", "OLECTRA",
    "ORIENTCEM", "PCBL", "PEL", "PFIZER", "PFC",
    "PIIND", "POLYMED", "POWERMECH", "PRAJIND", "PRESTIGE",
    "PRINCEPIPE", "PRSMJOHNS", "PVRINOX", "QUESS", "RADICO",
    "RAJESHEXPO", "RAMCOCEM", "RITES", "ROSSARI", "ROUTE",
    "SAFARI", "SANOFI", "SAPPHIRE", "SCHAEFFLER", "SEQUENT",
    "SHYAMMETL", "SOBHA", "SOLARA", "SPANDANA", "STARHEALTH",
    "STLTECH", "SUPRAJIT", "SUPREMEIND", "SURYAROSNI", "SWANENERGY",
    "SYMPHONY", "TANLA", "TASTYBITE", "TATACHEM", "TATAELXSI",
    "TATAINVEST", "THERMAX", "THYROCARE", "TORNTPHARM", "TORNTPOWER",
    "TTKPRESTIG", "UCOBANK", "UNIONBANK", "UNITDSPR", "UTIAMC",
    "VAIBHAVGBL", "VINATIORGA", "VLSFINANCE", "VSTIND", "WELCORP",
    "WHIRLPOOL", "WOCKPHARMA", "ZEEL", "ZENTEC", "ZYDUSLIFE",
]

NIFTY_SMALLCAP_100: List[str] = [
    "AARTIDRUGS", "ABSLBANETF", "ACCELYA", "ACCURACY", "ACRYSIL",
    "ADANIPOWER", "AFFLE", "AGROPHOS", "AHLEAST", "AHLUCONT",
    "AIIL", "ALEMBICLTD", "ALLCARGO", "AMBER", "AMJLAND",
    "ANGELONE", "ANUP", "APARINDS", "APOLLOTYRE", "APTUS",
    "ARCHIES", "ARCOTECH", "ARFIN", "ARTSON", "ASAHIINDIA",
    "ASHOKLEY", "ASTRAMICRO", "ATGL", "ATLAS", "AUTOMAXINDA",
    "AVANTIFEED", "AVINASH", "BASF", "BALAMINES", "BALMLAWRIE",
    "BANSALWIRE", "BARBEQUE", "BAYERCROP", "BEML", "BFUTILITIE",
    "BHAGERIA", "BHAKTIYOGA", "BIKAJI", "CAPACITE", "CARERATING",
    "CDSL", "CHEMCON", "CHEMFAB", "CHEMPLASTS", "CLEAN",
    "COCHINSHIP", "CONFIPET", "COSMOFILM", "CRAFTSMAN", "CREDITACC",
    "CRISIL", "CUB", "CYIENTDLM", "DATAPATTNS", "DCMSHRIRAM",
    "DELHIVERY", "DEVYANI", "DHANI", "DHANUKA", "DYNAMATECH",
    "EIHOTEL", "ELECON", "EMAMILTD", "EMCURE", "EPIGRAL",
    "ESABINDIA", "ESAB", "EVERESTIND", "FINEORG", "FINPIPE",
    "FIVESTAR", "FLOTATION", "FMGOETZE", "FORCEMOT", "GABRIEL",
    "GALAXYSURF", "GARFIBRES", "GATEWAY", "GFL", "GHCL",
    "GICRE", "GIRNARFOOD", "GMM", "GODFRYPHLP", "GRINDWELL",
    "GRMOVER", "GSFC", "GULFOILLUB", "HBLPOWER", "HERITGFOOD",
    "HIMATSEIDE", "HINDCOPPER", "HINDWAREAP", "HPL", "IBREALEST",
]

# ---------------------------------------------------------------------------
# Sectoral Indices
# ---------------------------------------------------------------------------

NIFTY_BANK: List[str] = [
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN",
    "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "AUBANK",
    "PNB", "BANKBARODA", "CANBK", "UNIONBANK", "INDIANB",
]

NIFTY_IT: List[str] = [
    "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM",
    "LTIM", "MPHASIS", "COFORGE", "PERSISTENT", "LTTS",
    "MINDTREE", "MASTEK", "KPITTECH", "CYIENT", "NIIT",
]

NIFTY_PHARMA: List[str] = [
    "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA",
    "BIOCON", "ALKEM", "LUPIN", "TORNTPHARM", "GLENMARK",
    "LALPATHLAB", "METROPOLIS", "AJANTPHARM", "GRANULES", "ZYDUSLIFE",
    "NATCOPHARM", "PFIZER", "SANOFI", "GLAXO", "WOCKPHARMA",
]

NIFTY_AUTO: List[str] = [
    "TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "EICHERMOT",
    "HEROMOTOCO", "TVSMOTOR", "ASHOKLEY", "APOLLOTYRE", "MRF",
    "CEATLTD", "EXIDEIND", "MOTHERSON", "BOSCHLTD", "BHARATFORG",
    "ESCORTS", "TIINDIA", "JKTYRE", "FORCEMOT", "GABRIEL",
]

NIFTY_FMCG: List[str] = [
    "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR",
    "MARICO", "GODREJCP", "COLPAL", "TATACONSUM", "EMAMILTD",
    "MCDOWELL-N", "RADICO", "VBL", "BIKAJI", "VARUN",
]

NIFTY_METAL: List[str] = [
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "COALINDIA", "NMDC",
    "VEDL", "SAIL", "NATIONALUM", "HINDCOPPER", "WELCORP",
    "JINDALSAW", "JSPL", "EDELSTEEL", "RATNAMANI", "APL",
]

NIFTY_ENERGY: List[str] = [
    "RELIANCE", "ONGC", "BPCL", "IOC", "GAIL",
    "NTPC", "POWERGRID", "ADANIGREEN", "TATAPOWER", "NHPC",
    "PETRONET", "GSPL", "GUJGASLTD", "ATGL", "IGL",
]

NIFTY_REALTY: List[str] = [
    "DLF", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD", "PRESTIGE",
    "SOBHA", "MAHLIFE", "BRIGADE", "KOLTEPATIL", "NESCO",
]

NIFTY_INFRA: List[str] = [
    "LT", "ADANIPORTS", "BHARTIARTL", "POWERGRID", "NTPC",
    "SIEMENS", "ABB", "CUMMINSIND", "ENGINERSIN", "CONCOR",
    "IRCTC", "RITES", "NBCC", "HUDCO", "RECLTD",
]

# ---------------------------------------------------------------------------
# F&O Stocks (NSE Futures & Options eligible — ~200 stocks)
# ---------------------------------------------------------------------------

FNO_STOCKS: List[str] = [
    # Large caps (Nifty 50 + Next 50 F&O eligible)
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC",
    "LT", "SBIN", "KOTAKBANK", "AXISBANK", "HINDUNILVR", "BAJFINANCE",
    "MARUTI", "ASIANPAINT", "HCLTECH", "SUNPHARMA", "TITAN", "ULTRACEMCO",
    "WIPRO", "NTPC", "ONGC", "M&M", "POWERGRID", "NESTLEIND", "TATAMOTORS",
    "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV",
    "GRASIM", "HINDALCO", "DRREDDY", "CIPLA", "TECHM", "INDUSINDBK",
    "EICHERMOT", "BRITANNIA", "BPCL", "DIVISLAB", "HEROMOTOCO", "APOLLOHOSP",
    "TATACONSUM", "UPL", "BAJAJ-AUTO", "SBILIFE", "HDFCLIFE", "LTIM",
    # Additional F&O eligible
    "AMBUJACEM", "AUROPHARMA", "BANDHANBNK", "BANKBARODA", "BEL",
    "BERGEPAINT", "BIOCON", "BOSCHLTD", "CANBK", "CHOLAFIN",
    "COLPAL", "DABUR", "DMART", "DLF", "GAIL",
    "GODREJCP", "HAVELLS", "ICICIGI", "ICICIPRULI", "INDUSTOWER",
    "LICHSGFIN", "LUPIN", "MCX", "MUTHOOTFIN", "NAUKRI",
    "NYKAA", "OFSS", "PAGEIND", "PAYTM", "PETRONET",
    "PIDILITIND", "PNB", "RECLTD", "SAIL", "SHREECEM",
    "SIEMENS", "SRF", "TATACOMM", "TATAELXSI", "TATACHEM",
    "TRENT", "TVSMOTOR", "VEDL", "VOLTAS", "ZOMATO",
    "IDFCFIRSTB", "FEDERALBNK", "INDIAMART", "IRCTC", "CONCOR",
    "GMRINFRA", "OBEROIRLTY", "PRESTIGE", "GODREJPROP", "PHOENIXLTD",
    "ASHOKLEY", "MRF", "CEATLTD", "EXIDEIND", "APOLLOTYRE",
    "ESCORTS", "TVSMOTOR", "MOTHERSON", "BHARATFORG", "BOSCHLTD",
    "ALKEM", "TORNTPHARM", "ZYDUSLIFE", "GLENMARK", "NATCOPHARM",
    "AJANTPHARM", "GRANULES", "LALPATHLAB", "METROPOLIS", "DIVISLAB",
    "PERSISTENT", "COFORGE", "KPITTECH", "LTTS", "CYIENT",
    "MPHASIS", "MASTEK", "HAPPSTMNDS", "TANLA", "ROUTE",
    "DEEPAKNTR", "GNFC", "AARTIIND", "ATUL", "PIIND",
    "VINATIORGA", "FINEORG", "CLEAN", "NOCIL", "PCBL",
    "BALKRISIND", "CUMMINSIND", "THERMAX", "ELGIEQUIP", "ABB",
    "HONAUT", "AIAENG", "GRINDWELL", "SCHAEFFLER", "TIMKEN",
    "INDHOTEL", "EIHOTEL", "LEMONTREE", "MAHLIFE", "BRIGADE",
    "SOBHA", "KOLTEPATIL", "SUNCLAYLTD", "HUDCO", "NBCC",
    "ENGINERSIN", "RITES", "BEML", "RAILVIKAS", "IRFC",
    "POLYCAB", "KEI", "HBLPOWER", "KALPATPOWR", "POWERMECH",
    "TORNTPOWER", "TATAPOWER", "ADANIGREEN", "NHPC", "SJVN",
    "ATGL", "IGL", "MGL", "GSPL", "GUJGASLTD",
    "CDSL", "BSE", "ISEC", "ANGELONE", "MOTILALOFS",
    "CAMS", "KFINTECH", "IRCTC", "INDIGRID", "POWERGRID",
]

# ---------------------------------------------------------------------------
# BSE 100 Additional (non-overlapping with NSE lists)
# ---------------------------------------------------------------------------

BSE_100_ADDITIONAL: List[str] = [
    "ZENSARTECH", "KALYANI", "SUNDARMFIN", "SUNDRMFAST", "WABAG",
    "RAJRATAN", "DPABHUSHAN", "GILLETTE", "HEIDELBERG", "JKLAKSHMI",
    "JKCEMENT", "PRIMESECSV", "REDINGTON", "SUNDARAM", "TTML",
    "UFLEX", "USHAMART", "VESUVIUS", "VGUARD", "XPRO",
]

# ---------------------------------------------------------------------------
# Sector Mapping (symbol -> sector)
# ---------------------------------------------------------------------------

SECTOR_MAP: Dict[str, str] = {}

def _build_sector_map():
    sectors = {
        "Banking": NIFTY_BANK,
        "IT": NIFTY_IT,
        "Pharma": NIFTY_PHARMA,
        "Auto": NIFTY_AUTO,
        "FMCG": NIFTY_FMCG,
        "Metal": NIFTY_METAL,
        "Energy": NIFTY_ENERGY,
        "Realty": NIFTY_REALTY,
        "Infrastructure": NIFTY_INFRA,
    }
    for sector, stocks in sectors.items():
        for s in stocks:
            if s not in SECTOR_MAP:
                SECTOR_MAP[s] = sector

_build_sector_map()


# ---------------------------------------------------------------------------
# Universe builder
# ---------------------------------------------------------------------------

def get_full_universe(
    include_midcap: bool = True,
    include_smallcap: bool = False,
    include_fno_only: bool = False,
    live: bool = False,
    all_equity: bool = False,
) -> List[str]:
    """
    Returns the complete deduplicated stock universe.

    Parameters
    ----------
    include_midcap : bool
        Include Nifty Midcap 150 (default True)
    include_smallcap : bool
        Include Nifty Smallcap 100 (default False — adds noise for daily scans)
    include_fno_only : bool
        Return only F&O eligible stocks (overrides other flags)
    live : bool
        Attempt to fetch the live Nifty 500 list from NSE India (requires internet)
    all_equity : bool
        Fetch every NSE equity (EQ series, ~1900 symbols) + BSE-only equities.
        Results are cached for 24 h in .gate_cache/. Overrides other flags
        except include_fno_only.

    Returns
    -------
    List[str]
        Deduplicated list of NSE symbols (no .NS suffix).
        BSE-only symbols are returned with a .BO suffix.
    """
    if include_fno_only:
        return sorted(set(FNO_STOCKS))

    if all_equity:
        return _get_all_equity_universe()

    if live:
        live_list = _fetch_nse_live()
        if live_list:
            return live_list

    universe = set(NIFTY_50 + NIFTY_NEXT_50)
    if include_midcap:
        universe.update(NIFTY_MIDCAP_150)
    if include_smallcap:
        universe.update(NIFTY_SMALLCAP_100)
    universe.update(FNO_STOCKS)
    return sorted(universe)


def _get_all_equity_universe() -> List[str]:
    """
    Fetch the complete NSE + BSE equity universe and return a deduplicated list.

    NSE:  All EQ-series equities from NSE's EQUITY_L.csv (~1900 symbols).
    BSE:  BSE-only equities (not already on NSE), returned with .BO suffix.

    Both lists are cached to disk for 24 hours so repeated calls within the
    same day don't hit the network.
    """
    nse_syms = _fetch_all_nse_equity()
    if not nse_syms:
        # Graceful degradation — fall back to the full static list
        logger.warning("NSE full equity fetch failed — using static universe as fallback")
        nse_syms = sorted(
            set(NIFTY_50 + NIFTY_NEXT_50 + NIFTY_MIDCAP_150 + NIFTY_SMALLCAP_100 + FNO_STOCKS)
        )

    nse_set = set(nse_syms)
    bse_only = _fetch_all_bse_equity(nse_symbols=nse_set) or []

    combined = sorted(nse_set | set(bse_only))
    logger.info(
        "Full all-equity universe: %d NSE + %d BSE-only = %d total",
        len(nse_set), len(bse_only), len(combined),
    )
    return combined


# ---------------------------------------------------------------------------
# NSE full equity fetcher (EQUITY_L.csv)
# ---------------------------------------------------------------------------

def _fetch_all_nse_equity() -> Optional[List[str]]:
    """
    Download all NSE-listed equities (EQ series) from NSE's EQUITY_L.csv.

    The file is publicly available at:
      https://archives.nseindia.com/content/equities/EQUITY_L.csv

    Columns: SYMBOL, NAME OF COMPANY, SERIES, DATE OF LISTING, …
    We keep only rows where SERIES == "EQ" (main-board equities).

    Returns ~1900 symbols. Caches to .gate_cache/_univ_nse_all.txt for 24 h.
    """
    cached = _read_univ_cache("nse_all")
    if cached:
        logger.info("NSE full universe from cache: %d symbols", len(cached))
        return cached

    try:
        import urllib.request
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        symbols: List[str] = []
        for line in raw.splitlines()[1:]:   # skip header row
            parts = line.split(",")
            if len(parts) < 3:
                continue
            sym    = parts[0].strip().strip('"')
            series = parts[2].strip().strip('"')
            if sym and series == "EQ":
                symbols.append(sym)

        if len(symbols) >= 500:
            result = sorted(set(symbols))
            logger.info("Fetched %d NSE equity symbols (EQ series) from EQUITY_L.csv", len(result))
            _write_univ_cache("nse_all", result)
            return result

        logger.warning(
            "NSE EQUITY_L.csv returned only %d EQ symbols — file format may have changed",
            len(symbols),
        )

    except Exception as e:
        logger.warning("NSE EQUITY_L.csv fetch failed: %s", e)

    return None


# ---------------------------------------------------------------------------
# BSE full equity fetcher
# ---------------------------------------------------------------------------

def _fetch_all_bse_equity(nse_symbols: Optional[set] = None) -> Optional[List[str]]:
    """
    Download BSE equity list from BSE's public API and return symbols for
    stocks that are NOT already covered by the NSE list.

    Dual-listed stocks (on both NSE and BSE) are skipped — the NSE symbol
    is preferred because yfinance data is more reliable via `.NS`.

    BSE-only stocks are returned as "SYMBOL.BO" so that config.yf_symbol()
    can pass them through unchanged to yfinance.

    Results are cached for 24 hours.
    """
    cached = _read_univ_cache("bse_all")
    if cached:
        logger.info("BSE universe from cache: %d BSE-only symbols", len(cached))
        return cached

    nse_set: set = set(nse_symbols or [])
    raw_bse_symbols: dict = {}   # trading_symbol -> True

    try:
        import json
        import urllib.request

        base_url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
        common_headers = {
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

        # BSE classifies equities into groups: A (top liquid), B, T (trade-to-trade), X, XT
        for group in ["A", "B", "T", "X", "XT"]:
            try:
                url = (
                    f"{base_url}?Group={group}&Exportflag=1"
                    "&indexname=&scripname=&strsearch="
                )
                req = urllib.request.Request(url, headers=common_headers)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))

                # API may return a list or a dict with "Table" / "data" key
                items = (
                    data if isinstance(data, list)
                    else (
                        data.get("Table")
                        or data.get("Table1")
                        or data.get("data")
                        or []
                    )
                )

                for item in items:
                    # Try several known field names for the trading symbol
                    sym = (
                        item.get("scrip_cd")
                        or item.get("SCRIP_CD")
                        or item.get("Symbol")
                        or item.get("SYMBOL")
                        or ""
                    )
                    if isinstance(sym, str):
                        sym = sym.strip()
                    elif isinstance(sym, (int, float)):
                        sym = str(int(sym))
                    else:
                        continue

                    if sym:
                        raw_bse_symbols[sym] = True

            except Exception as e:
                logger.debug("BSE Group %s fetch failed: %s", group, e)

        if len(raw_bse_symbols) < 200:
            logger.warning(
                "BSE equity list returned only %d symbols — API may have changed format. "
                "Skipping BSE-only additions.",
                len(raw_bse_symbols),
            )
            return None

        # Build BSE-only list: exclude any symbol already in NSE list
        bse_only: List[str] = []
        for sym in sorted(raw_bse_symbols.keys()):
            if sym not in nse_set:
                bse_only.append(f"{sym}.BO")

        logger.info(
            "BSE fetch: %d total symbols, %d are BSE-only (not in NSE list)",
            len(raw_bse_symbols), len(bse_only),
        )
        result = sorted(set(bse_only))
        _write_univ_cache("bse_all", result)
        return result

    except Exception as e:
        logger.warning("BSE full equity fetch failed: %s", e)

    return None


def _fetch_nse_live() -> Optional[List[str]]:
    """
    Attempt to fetch the current Nifty 500 index constituents CSV from NSE India.
    Returns None on failure (caller falls back to static list).

    NSE CSV endpoint:
      https://archives.nseindia.com/content/indices/ind_nifty500list.csv
    """
    try:
        import urllib.request
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        symbols = []
        for line in raw.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) >= 3:
                sym = parts[2].strip().strip('"')
                if sym:
                    symbols.append(sym)
        if len(symbols) > 400:
            logger.info("Fetched %d symbols from NSE live list", len(symbols))
            return symbols
    except Exception as e:
        logger.warning("NSE live fetch failed: %s — using static universe", e)
    return None
