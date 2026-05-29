"""
universe/filters.py
====================
Chainable filter builder for the NSE/BSE stock universe.

Usage
-----
from gate_scanner.universe import UniverseFilter, get_full_universe

# All F&O stocks in Banking or IT sector, excluding PAYTM
symbols = (
    UniverseFilter(get_full_universe(include_fno_only=True))
    .by_sector(["Banking", "IT"])
    .exclude(["PAYTM"])
    .get()
)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .nse_universe import (
    NIFTY_50, NIFTY_NEXT_50, NIFTY_MIDCAP_150, NIFTY_SMALLCAP_100,
    FNO_STOCKS, NIFTY_BANK, NIFTY_IT, NIFTY_PHARMA, NIFTY_AUTO,
    NIFTY_FMCG, NIFTY_METAL, NIFTY_ENERGY, NIFTY_REALTY, NIFTY_INFRA,
    BSE_100_ADDITIONAL, SECTOR_MAP,
)

# Internal name → list mapping for by_index()
_INDEX_MAP: Dict[str, List[str]] = {
    "NIFTY_50":        NIFTY_50,
    "NIFTY_NEXT_50":   NIFTY_NEXT_50,
    "NIFTY_MIDCAP_150": NIFTY_MIDCAP_150,
    "NIFTY_SMALLCAP_100": NIFTY_SMALLCAP_100,
    "FNO":             FNO_STOCKS,
    "NIFTY_BANK":      NIFTY_BANK,
    "NIFTY_IT":        NIFTY_IT,
    "NIFTY_PHARMA":    NIFTY_PHARMA,
    "NIFTY_AUTO":      NIFTY_AUTO,
    "NIFTY_FMCG":      NIFTY_FMCG,
    "NIFTY_METAL":     NIFTY_METAL,
    "NIFTY_ENERGY":    NIFTY_ENERGY,
    "NIFTY_REALTY":    NIFTY_REALTY,
    "NIFTY_INFRA":     NIFTY_INFRA,
    "BSE_100":         BSE_100_ADDITIONAL,
}


class UniverseFilter:
    """
    Wraps a symbol list and narrows it through chainable filter operations.
    All methods return `self` for chaining. Call `.get()` to retrieve results.
    """

    def __init__(
        self,
        symbols: List[str],
        sector_map: Optional[Dict[str, str]] = None,
    ):
        self._symbols: List[str] = list(symbols)
        self._sector_map: Dict[str, str] = sector_map if sector_map is not None else SECTOR_MAP

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    def by_sector(self, sectors: List[str]) -> "UniverseFilter":
        """Keep only symbols whose sector (from SECTOR_MAP) is in `sectors`."""
        sector_set = {s.lower() for s in sectors}
        self._symbols = [
            sym for sym in self._symbols
            if self._sector_map.get(sym, "").lower() in sector_set
        ]
        return self

    def by_index(self, index: str) -> "UniverseFilter":
        """
        Keep only symbols belonging to the named index.

        Valid index names:
          NIFTY_50, NIFTY_NEXT_50, NIFTY_MIDCAP_150, NIFTY_SMALLCAP_100,
          FNO, NIFTY_BANK, NIFTY_IT, NIFTY_PHARMA, NIFTY_AUTO, NIFTY_FMCG,
          NIFTY_METAL, NIFTY_ENERGY, NIFTY_REALTY, NIFTY_INFRA, BSE_100
        """
        index_list = _INDEX_MAP.get(index.upper())
        if index_list is None:
            raise ValueError(
                f"Unknown index '{index}'. Valid names: {sorted(_INDEX_MAP)}"
            )
        index_set = set(index_list)
        self._symbols = [sym for sym in self._symbols if sym in index_set]
        return self

    def exclude(self, blacklist: List[str]) -> "UniverseFilter":
        """Remove specific symbols from the working list."""
        bl = set(blacklist)
        self._symbols = [sym for sym in self._symbols if sym not in bl]
        return self

    def include(self, extra: List[str]) -> "UniverseFilter":
        """Add extra symbols (de-duplicated) to the working list."""
        existing = set(self._symbols)
        self._symbols = self._symbols + [s for s in extra if s not in existing]
        return self

    # ------------------------------------------------------------------
    # Terminal
    # ------------------------------------------------------------------

    def get(self) -> List[str]:
        """Return the current filtered symbol list — deduplicated and sorted."""
        return sorted(set(self._symbols))

    def __len__(self) -> int:
        return len(self._symbols)

    def __repr__(self) -> str:
        return f"UniverseFilter({len(self._symbols)} symbols)"
