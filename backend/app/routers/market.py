from fastapi import APIRouter, Depends, Query, HTTPException
import redis.asyncio as aioredis

from app.dependencies import redis_client
from app.services.price_service import get_price, get_bulk_prices

router = APIRouter(tags=["market"])


@router.get("/price/{symbol}")
async def single_price(
    symbol: str,
    redis: aioredis.Redis = Depends(redis_client),
):
    price = await get_price(symbol.upper(), redis)
    if price is None:
        raise HTTPException(status_code=503, detail=f"Price unavailable for {symbol}")
    return {"symbol": symbol.upper(), "price": price}


@router.get("/prices")
async def bulk_prices(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    redis: aioredis.Redis = Depends(redis_client),
):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not sym_list:
        raise HTTPException(status_code=422, detail="No symbols provided")
    if len(sym_list) > 50:
        raise HTTPException(status_code=422, detail="Max 50 symbols per request")
    prices = await get_bulk_prices(sym_list, redis)
    return {"prices": prices}
