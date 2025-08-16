from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import JSONResponse

import time
from datetime import datetime, timedelta

from src.app.core.config import get_alpaca
from src.app.schemas.candle import Candle
from src.app.schemas.levels import SRResponse
from src.app.services.candles_service import CandlesService, get_candles_service
from src.app.services.cache_service import get_candles_cache

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Candles"],
    prefix="/candles",
    responses={
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limited"},
        502: {"description": "Upstream data provider error"},
    },
)

def _make_json_serializable(data):
    """Convert datetime objects to ISO strings for JSON serialization"""
    if isinstance(data, dict):
        return {k: _make_json_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_make_json_serializable(item) for item in data]
    elif hasattr(data, 'isoformat'):  # datetime objects
        return data.isoformat()
    else:
        return data

@router.get(
    "/{symbol}",
    summary="Get recent daily bars",
    description="Fetches recent **1D** OHLCV bars for one or more lookbacks (e.g., 7, 30, 90 days).",
    response_description="Map of window size (days) to an array of candles.",
    tags=["Candles"],
)
async def get_bars_multi(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_candles_service),
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
    Optimized with parallel processing for multiple timeframes.
    """
    # Check cache first for ultra-fast responses
    cache_key = f"candles:{symbol.upper()}:{days}"
    cached_data = await get_candles_cache().get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service with parallel processing
    try:
        windows = sorted({int(x.strip()) for x in days.split(",") if x.strip()})
        
        # Parallel processing for multiple timeframes
        tasks = [svc.get_recent_bars(symbol, days=w, timeframe="1Day") for w in windows]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build response with error handling
        out: Dict[int, List[Dict]] = {}
        for w, result in zip(windows, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch {w}-day bars for {symbol}: {result}")
                out[w] = []  # Empty array on error
            else:
                # Convert Candle objects to dictionaries for JSON serialization
                out[w] = [candle.model_dump(mode='json') for candle in result]
        
        # Cache the result for future requests
        await get_candles_cache().set(cache_key, out)
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=out, headers={"X-Cache": "MISS"})
        
    except Exception as e:
        # REMOVE FALLBACK - let errors surface
        logger.error(f"Failed to get candles for {symbol}: {e}")
        raise

@router.get(
    "/{symbol}/levels",
    summary="Get aggregated support/resistance",
    description=(
        "Aggregates S/R from multiple lookbacks (default **7/30/90** days).\n"
        "Uses swing detection + ATR-tolerant clustering, then scores by touches and recency."
    ),
    response_description="Aggregated S/R levels with strength scores.",
    tags=["Candles"],
)
async def get_levels(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_candles_service),
    days: str = Query(
        "7,30,90",
        description="Comma-separated lookbacks used for aggregation.",
        examples={
            "default": {"summary": "Common windows", "value": "7,30,90"},
            "quick": {"summary": "Quick analysis", "value": "30"},
        },
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
    # Check cache first for ultra-fast responses
    cache_key = f"levels:{symbol.upper()}:{days}:{maxLevels}:{swingWindow}:{toleranceFactor}"
    cached_data = await get_candles_cache().get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        windows = [int(x.strip()) for x in days.split(",") if x.strip()]
        result = await svc.get_aggregated_sr(
            symbol=symbol,
            windows=windows,
            max_levels=maxLevels,
            swing_window=swingWindow,
            tolerance_factor=toleranceFactor,
        )
        
        # Cache the result for future requests
        await get_candles_cache().set(cache_key, result.model_dump(mode='json'))
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=result.model_dump(mode='json'), headers={"X-Cache": "MISS"})
        
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} levels due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

# ---- shared headers ----
def set_rate_limit_headers(resp: Response, limit: int = 60, remaining: int = 59, reset_seconds: int = 60):
    now_epoch = int(time.time())
    resp.headers["X-RateLimit-Limit"] = str(limit)
    resp.headers["X-RateLimit-Remaining"] = str(remaining)
    resp.headers["X-RateLimit-Reset"] = str(now_epoch + reset_seconds)

# ---- cache management ----
@router.delete("/cache/{symbol}", tags=["Candles"])
async def invalidate_cache(
    symbol: str = Path(..., description="Ticker symbol to invalidate cache for"),
):
    """Invalidate cache for a specific symbol (admin/debug endpoint)"""
    symbol_upper = symbol.upper()
    
    # Get cache instance
    cache = get_candles_cache()
    
    # Invalidate all cache keys for this symbol using pattern deletion
    patterns_to_invalidate = [
        f"candles:{symbol_upper}:*",
        f"levels:{symbol_upper}:*",
        f"indicators:{symbol_upper}:*",
        f"patterns:{symbol_upper}:*",
        f"pivots:{symbol_upper}:*",
        f"multi_pivots:{symbol_upper}:*"
    ]
    
    total_invalidated = 0
    for pattern in patterns_to_invalidate:
        try:
            deleted_count = await cache.delete_pattern(pattern)
            total_invalidated += deleted_count
        except Exception as e:
            logger.warning(f"Failed to invalidate pattern {pattern}: {e}")
    
    return {
        "message": f"Cache invalidated for {symbol_upper}", 
        "status": "success",
        "patterns_processed": len(patterns_to_invalidate),
        "total_invalidated": total_invalidated
    }

@router.get(
    "/{symbol}/indicators",
    summary="Get technical indicators",
    description="Calculate popular technical indicators including SMA, EMA, RSI, MACD, and Bollinger Bands.",
    response_description="Technical indicators with calculated values.",
    tags=["Candles"],
)
async def get_technical_indicators(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_candles_service),
    indicators: str = Query(
        "sma,ema,rsi,macd,bbands,atr",
        description="Comma-separated list of indicators to calculate.",
        examples={
            "default": {"summary": "All indicators", "value": "sma,ema,rsi,macd,bbands,atr"},
            "trend": {"summary": "Trend indicators", "value": "sma,ema,macd"},
            "momentum": {"summary": "Momentum indicators", "value": "rsi,atr"},
        },
    ),
    period: int = Query(20, ge=5, le=200, description="Period for calculations (default: 20)"),
    days: int = Query(100, ge=30, le=500, description="Number of days to look back (default: 100)"),
):
    """
    Calculate technical indicators for technical analysis.
    
    Available indicators:
    - **sma**: Simple Moving Average
    - **ema**: Exponential Moving Average  
    - **rsi**: Relative Strength Index (14-period default)
    - **macd**: Moving Average Convergence Divergence
    - **bbands**: Bollinger Bands (20-period, 2σ default)
    - **atr**: Average True Range (14-period default)
    """
    # Check cache first for ultra-fast responses
    cache_key = f"indicators:{symbol.upper()}:{indicators}:{period}:{days}"
    cached_data = await get_candles_cache().get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        # Parse indicators
        indicator_list = [i.strip().lower() for i in indicators.split(",") if i.strip()]
        
        # Validate indicators
        valid_indicators = {"sma", "ema", "rsi", "macd", "bbands", "atr"}
        invalid_indicators = set(indicator_list) - valid_indicators
        if invalid_indicators:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid indicators: {', '.join(invalid_indicators)}. Valid options: {', '.join(valid_indicators)}"
            )
        
        # Get technical indicators
        result = await svc.get_technical_indicators(
            symbol=symbol,
            indicators=indicator_list,
            period=period,
            days=days
        )
        
        # Ensure result is JSON serializable by converting datetime objects
        serializable_result = _make_json_serializable(result)
        
        # Cache the serializable result for future requests
        await get_candles_cache().set(cache_key, serializable_result)
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=serializable_result, headers={"X-Cache": "MISS"})
        
    except HTTPException:
        raise
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} indicators due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get(
    "/{symbol}/patterns",
    summary="Get candlestick patterns",
    description="Detect popular candlestick patterns including Doji, Hammer, and Engulfing patterns.",
    response_description="Detected candlestick patterns with timestamps and confidence.",
    tags=["Candles"],
)
async def get_candlestick_patterns(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_candles_service),
    patterns: str = Query(
        "doji,hammer,engulfing",
        description="Comma-separated list of patterns to detect.",
        examples={
            "default": {"summary": "All patterns", "value": "doji,hammer,engulfing"},
            "reversal": {"summary": "Reversal patterns", "value": "hammer,engulfing"},
            "indecision": {"summary": "Indecision patterns", "value": "doji"},
        },
    ),
    days: int = Query(30, ge=10, le=100, description="Number of days to look back (default: 30)"),
):
    """
    Detect candlestick patterns for technical analysis.
    
    Available patterns:
    - **doji**: Indecision pattern (open and close are very close)
    - **hammer**: Bullish reversal pattern (long lower shadow, small body)
    - **engulfing**: Strong reversal pattern (bullish or bearish)
    
    Each pattern includes:
    - timestamp: When the pattern occurred
    - position: Position in the data series
    - confidence: Pattern confidence level
    - type: For engulfing patterns (bullish/bearish)
    """
    # Check cache first for ultra-fast responses
    cache_key = f"patterns:{symbol.upper()}:{patterns}:{days}"
    cached_data = await get_candles_cache().get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        # Parse patterns
        pattern_list = [p.strip().lower() for p in patterns.split(",") if p.strip()]
        
        # Validate patterns
        valid_patterns = {"doji", "hammer", "engulfing"}
        invalid_patterns = set(pattern_list) - valid_patterns
        if invalid_patterns:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid patterns: {', '.join(invalid_patterns)}. Valid options: {', '.join(valid_patterns)}"
            )
        
        # Get candlestick patterns
        result = await svc.get_candlestick_patterns(
            symbol=symbol,
            patterns=pattern_list,
            days=days
        )
        
        # Ensure result is JSON serializable by converting datetime objects
        serializable_result = _make_json_serializable(result)
        
        # Cache the serializable result for future requests
        await get_candles_cache().set(cache_key, serializable_result)
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=serializable_result, headers={"X-Cache": "MISS"})
        
    except HTTPException:
        raise
    except Exception as e:
        # REMOVE FALLBACK - let errors surface
        logger.error(f"Failed to get candlestick patterns for {symbol}: {e}")
        raise

@router.get(
    "/{symbol}/pivots",
    summary="Get pivot points",
    description="Calculate pivot points for support and resistance levels using multiple methods.",
    response_description="Pivot point levels for the specified timeframe and method.",
    tags=["Candles"],
)
async def get_pivot_points(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_candles_service),
    timeframe: str = Query(
        "daily",
        description="Timeframe for pivot point calculation.",
        examples={
            "daily": {"summary": "Daily pivots", "value": "daily"},
            "weekly": {"summary": "Weekly pivots", "value": "weekly"},
            "monthly": {"summary": "Monthly pivots", "value": "monthly"},
        },
    ),
    method: str = Query(
        "standard",
        description="Pivot point calculation method.",
        examples={
            "standard": {"summary": "Standard (Floor Trading)", "value": "standard"},
            "fibonacci": {"summary": "Fibonacci", "value": "fibonacci"},
            "camarilla": {"summary": "Camarilla", "value": "camarilla"},
            "woodie": {"summary": "Woodie", "value": "woodie"},
        },
    ),
    periods: int = Query(1, ge=1, le=5, description="Number of periods to calculate (default: 1)"),
):
    """
    Calculate pivot points for technical analysis.
    
    **Pivot Point Methods:**
    - **Standard**: Traditional floor trading method (H+L+C)/3
    - **Fibonacci**: Uses Fibonacci ratios (0.382, 0.618, 1.000)
    - **Camarilla**: Intraday trading levels (1.1/12, 1.1/6, 1.1/4)
    - **Woodie**: Modified standard with close price emphasis
    
    **Support & Resistance Levels:**
    - **Pivot**: Central pivot point
    - **R1, R2, R3**: Resistance levels (above pivot)
    - **S1, S2, S3**: Support levels (below pivot)
    
    **Use Cases:**
    - Entry/exit point identification
    - Stop-loss placement
    - Risk management
    - Day trading strategies
    """
    # Check cache first for ultra-fast responses
    cache_key = f"pivots:{symbol.upper()}:{timeframe}:{method}:{periods}"
    cached_data = await get_candles_cache().get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        # Validate timeframe
        valid_timeframes = {"daily", "weekly", "monthly"}
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid timeframe: {timeframe}. Valid options: {', '.join(valid_timeframes)}"
            )
        
        # Validate method
        valid_methods = {"standard", "fibonacci", "camarilla", "woodie"}
        if method not in valid_methods:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid method: {method}. Valid options: {', '.join(valid_methods)}"
            )
        
        # Get pivot points
        result = await svc.get_pivot_points(
            symbol=symbol,
            timeframe=timeframe,
            method=method,
            periods=periods
        )
        
        # Ensure result is JSON serializable by converting datetime objects
        serializable_result = _make_json_serializable(result)
        
        # Cache the serializable result for future requests
        await get_candles_cache().set(cache_key, serializable_result, ttl_seconds=3600)  # 1 hour for pivot points
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=serializable_result, headers={"X-Cache": "MISS"})
        
    except HTTPException:
        raise
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} pivot points due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get(
    "/{symbol}/pivots/multi",
    summary="Get multi-timeframe pivot points",
    description="Calculate pivot points for all timeframes (daily, weekly, monthly) using multiple methods.",
    response_description="Pivot point levels for all timeframes and methods.",
    tags=["Candles"],
)
async def get_multi_timeframe_pivots(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_candles_service),
    methods: str = Query(
        "standard,fibonacci",
        description="Comma-separated list of pivot point methods.",
        examples={
            "standard": {"summary": "Standard only", "value": "standard"},
            "fibonacci": {"summary": "Fibonacci only", "value": "fibonacci"},
            "all": {"summary": "All methods", "value": "standard,fibonacci,camarilla,woodie"},
        },
    ),
):
    """
    Calculate pivot points for all timeframes simultaneously.
    
    **Available Timeframes:**
    - **Daily**: 30 days of daily data
    - **Weekly**: 52 weeks of weekly data  
    - **Monthly**: 24 months of monthly data
    
    **Available Methods:**
    - **Standard**: Traditional floor trading
    - **Fibonacci**: Fibonacci ratio-based
    - **Camarilla**: Intraday trading levels
    - **Woodie**: Modified standard method
    
    **Use Cases:**
    - Multi-timeframe analysis
    - Swing trading strategies
    - Position sizing decisions
    - Risk management across timeframes
    """
    # Check cache first for ultra-fast responses
    cache_key = f"multi_pivots:{symbol.upper()}:{methods}"
    cached_data = await get_candles_cache().get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        # Parse methods
        method_list = [m.strip().lower() for m in methods.split(",") if m.strip()]
        
        # Validate methods
        valid_methods = {"standard", "fibonacci", "camarilla", "woodie"}
        invalid_methods = set(method_list) - valid_methods
        if invalid_methods:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid methods: {', '.join(invalid_methods)}. Valid options: {', '.join(valid_methods)}"
            )
        
        # Get multi-timeframe pivot points
        result = await svc.get_multi_timeframe_pivots(
            symbol=symbol,
            methods=method_list
        )
        
        # Ensure result is JSON serializable by converting datetime objects
        serializable_result = _make_json_serializable(result)
        
        # Cache the serializable result for future requests
        await get_candles_cache().set(cache_key, serializable_result, ttl_seconds=3600)  # 1 hour for multi-timeframe pivots
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=serializable_result, headers={"X-Cache": "MISS"})
        
    except HTTPException:
        raise
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} multi-timeframe pivots due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get("/cache/status", tags=["Candles"])
async def get_cache_status():
    """Get cache statistics and status"""
    cache = get_candles_cache()
    stats = cache.get_stats()
    
    return {
        "cache_name": stats["cache_name"],
        "cache_size": stats["memory_cache_size"],
        "ttl_seconds": stats["ttl_seconds"],
        "total_requests": stats["total_requests"],
        "cache_hits": stats["cache_hits"],
        "cache_misses": stats["cache_misses"],
        "hit_rate_percent": stats["cache_hit_rate_percent"],
        "redis_hits": stats["redis_hits"],
        "memory_hits": stats["memory_hits"],
        "redis_errors": stats["redis_errors"],
        "status": "active"
    }
