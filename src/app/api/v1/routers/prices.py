from __future__ import annotations

from typing import List, Dict
import time
from fastapi import APIRouter, Response, Depends, Query, Path

from src.app.core.config import get_alpaca
from src.app.schemas.candle import Candle
from src.app.services.prices_service import PricesService
from src.app.schemas.price_quote import PriceQuote
from src.app.schemas.levels import SRResponse

router = APIRouter(
    tags=["Prices"],
    prefix="",
    responses={
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limited"},
        502: {"description": "Upstream data provider error"},
    },
)

@router.get(
    "/prices/{symbol}",
    summary="Get current quote",
    description="Returns latest trade price, bid/ask, session OHLC, volume, previous close, and percent change.",
    response_description="Price quote snapshot.",
    response_model=PriceQuote,
    response_model_exclude_none=True,
    tags=["Prices"],
)
async def get_current_price(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`, `BTC-USD`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc: PricesService = Depends(get_alpaca),
):
    """
    Notes:
    - Backed by provider snapshot (latest trade + latest quote + daily bars).
    - Consider a short TTL cache (1–5s) to reduce provider load.
    """
    set_rate_limit_headers(resp)
    return await svc.get_price_quote(symbol)

@router.get(
    "/prices/{symbol}/change",
    summary="Get daily percent change",
    description="Percent change vs. previous daily close (e.g., `1.23` = +1.23%).",
    response_description="Raw percent change.",
    response_model=float,
    tags=["Prices"],
)
async def get_daily_change(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`, `BTC-USD`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc: PricesService = Depends(get_alpaca),
):
    set_rate_limit_headers(resp)
    return await svc.get_daily_change_percent(symbol)

@router.get(
    "/prices/{symbol}/bars",
    summary="Get recent daily bars",
    description="Fetches recent **1D** OHLCV bars for one or more lookbacks (e.g., 7, 30, 90 days).",
    response_description="Map of window size (days) to an array of candles.",
    response_model=Dict[int, List[Candle]],
    response_model_exclude_none=True,
    tags=["Prices"],
)
async def get_bars_multi(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc: PricesService = Depends(get_alpaca),
    days: str = Query(
        "7,30,90",
        description="Comma-separated lookbacks (days).",
        examples={
            "default": {"summary": "Common windows", "value": "7,30,90"},
            "short": {"summary": "Short-only", "value": "7"},
            "custom": {"summary": "Custom mix", "value": "20,60"},
        },
    ),
):
    """
    Use this to power light analytics or client-side charts.
    """
    set_rate_limit_headers(resp)
    windows = sorted({int(x.strip()) for x in days.split(",") if x.strip()})
    out: Dict[int, List[Candle]] = {}
    for w in windows:
        out[w] = await svc.get_recent_bars(symbol, days=w, timeframe="1Day")
    return out

@router.get(
    "/levels/{symbol}",
    summary="Get aggregated support/resistance",
    description=(
        "Aggregates S/R from multiple lookbacks (default **7/30/90** days).\n"
        "Uses swing detection + ATR-tolerant clustering, then scores by touches and recency."
    ),
    response_description="Aggregated S/R levels with strength scores.",
    response_model=SRResponse,
    response_model_exclude_none=True,
    tags=["Prices"],
)
async def get_levels(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc: PricesService = Depends(get_alpaca),
    days: str = Query(
        "7,30,90",
        description="Comma-separated lookbacks used for aggregation.",
        examples={"default": {"value": "7,30,90"}, "quick": {"value": "30"}},
    ),
    maxLevels: int = Query(10, ge=1, le=30, description="Maximum number of S/R levels to return."),
    swingWindow: int = Query(2, ge=1, le=5, description="Fractal window size for swing highs/lows."),
    toleranceFactor: float = Query(0.5, ge=0.1, le=2.0, description="Clustering tolerance multiplier on ATR."),
):
    """
    Output includes:
    - `levels[]`: price, side (`support|resistance`), touches, strength (0..1), first/last seen, sources (windows)
    - `atr14`: per-window ATR used for tolerance heuristics
    """
    set_rate_limit_headers(resp)
    windows = [int(x.strip()) for x in days.split(",") if x.strip()]
    return await svc.get_aggregated_sr(
        symbol=symbol,
        windows=windows,
        max_levels=maxLevels,
        swing_window=swingWindow,
        tolerance_factor=toleranceFactor,
    )

# ---- shared headers ----
def set_rate_limit_headers(resp: Response, limit: int = 60, remaining: int = 59, reset_seconds: int = 60):
    now_epoch = int(time.time())
    resp.headers["X-RateLimit-Limit"] = str(limit)
    resp.headers["X-RateLimit-Remaining"] = str(remaining)
    resp.headers["X-RateLimit-Reset"] = str(now_epoch + reset_seconds)