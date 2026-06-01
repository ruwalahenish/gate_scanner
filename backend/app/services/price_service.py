"""
Live price fetching with Redis cache (60s TTL during market hours).
Uses yfinance fast_info — lightweight, no full historical fetch needed.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import redis.asyncio as aioredis
import structlog

log = structlog.get_logger()
_executor = ThreadPoolExecutor(max_workers=4)


def _fetch_price_sync(symbol: str) -> float | None:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol if "." in symbol else f"{symbol}.NS")
        price = ticker.fast_info.last_price
        return float(price) if price else None
    except Exception as e:
        log.warning("price_fetch_failed", symbol=symbol, error=str(e))
        return None


def _fetch_prices_sync(symbols: list[str]) -> dict[str, float]:
    import yfinance as yf
    ns_symbols = [s if "." in s else f"{s}.NS" for s in symbols]
    result: dict[str, float] = {}
    try:
        tickers = yf.Tickers(" ".join(ns_symbols))
        for orig, ns in zip(symbols, ns_symbols):
            try:
                price = tickers.tickers[ns].fast_info.last_price
                if price:
                    result[orig] = float(price)
            except Exception:
                pass
    except Exception:
        # Fallback: fetch one by one
        for sym in symbols:
            p = _fetch_price_sync(sym)
            if p:
                result[sym] = p
    return result


async def get_price(symbol: str, redis: aioredis.Redis) -> float | None:
    cache_key = f"price:{symbol}"
    cached = await redis.get(cache_key)
    if cached:
        return float(cached)
    loop = asyncio.get_event_loop()
    price = await loop.run_in_executor(_executor, _fetch_price_sync, symbol)
    if price:
        await redis.setex(cache_key, 60, str(price))
    return price


async def get_bulk_prices(
    symbols: list[str], redis: aioredis.Redis
) -> dict[str, float]:
    if not symbols:
        return {}

    result: dict[str, float] = {}

    # Fetch all cached prices in a single MGET round-trip instead of one GET per symbol
    keys = [f"price:{s}" for s in symbols]
    cached_values = await redis.mget(*keys)

    missing: list[str] = []
    for sym, cached in zip(symbols, cached_values):
        if cached is not None:
            result[sym] = float(cached)
        else:
            missing.append(sym)

    if missing:
        loop = asyncio.get_event_loop()
        fetched = await loop.run_in_executor(_executor, _fetch_prices_sync, missing)
        pipe = redis.pipeline()
        for sym, price in fetched.items():
            result[sym] = price
            pipe.setex(f"price:{sym}", 60, str(price))
        if fetched:
            await pipe.execute()

    return result
