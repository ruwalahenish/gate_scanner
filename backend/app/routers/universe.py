from fastapi import APIRouter, Query
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(tags=["universe"])
_ex = ThreadPoolExecutor(max_workers=2)


def _get_universe_sync() -> list[str]:
    from gate_scanner.universe import get_full_universe
    return get_full_universe()


def _search_sync(query: str) -> list[str]:
    from gate_scanner.universe import get_full_universe
    q = query.upper()
    return [s for s in get_full_universe() if q in s][:20]


@router.get("")
async def get_universe():
    loop = asyncio.get_event_loop()
    symbols = await loop.run_in_executor(_ex, _get_universe_sync)
    return {"count": len(symbols), "symbols": symbols}


@router.get("/search")
async def search_universe(
    q: str = Query(..., min_length=1, max_length=20)
):
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(_ex, _search_sync, q)
    return {"results": results}
