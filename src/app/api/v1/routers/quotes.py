from __future__ import annotations

from typing import List, Dict
import time
from fastapi import APIRouter, Response, Depends, Query, Path, HTTPException
from fastapi.responses import JSONResponse

import logging
from src.app.core.config import get_alpaca
from src.app.services.quotes_service import get_quotes_service
from src.app.services.cache_service import get_quotes_cache

logger = logging.getLogger(__name__)

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

# Remove the custom QuoteCache class and use the factory instead
# Global cache instance
quote_cache = get_quotes_cache()

router = APIRouter(
    tags=["Quotes"],
    prefix="/quotes",
    responses={
        401: {"description": "Unauthorized"},
        429: {"description": "Rate limited"},
        502: {"description": "Upstream data provider error"},
    },
)

@router.get(
    "/{symbol}",
    summary="Get current quote",
    description="Returns latest trade price, bid/ask, session OHLC, volume, previous close, and percent change.",
    response_description="Price quote snapshot.",
    tags=["Quotes"],
)
async def get_current_quote(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`, `BTC-USD`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_quotes_service),
):
    """
    Notes:
    - Backed by provider snapshot (latest trade + latest quote + daily bars).
    - Uses 5-second TTL cache to reduce provider load and improve latency.
    """
    # Check cache first for ultra-fast responses
    cache_key = f"quote:{symbol.upper()}"
    cached_data = await quote_cache.get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        quote = await svc.get_price_quote(symbol)
        quote_data = quote.model_dump(mode='json')
        
        # Cache the result for future requests
        await quote_cache.set(cache_key, quote_data)
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=quote_data, headers={"X-Cache": "MISS"})
        
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} quote due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get(
    "/{symbol}/change",
    summary="Get daily percent change",
    description="Percent change vs. previous daily close (e.g., `1.23` = +1.23%).",
    response_description="Raw percent change.",
    tags=["Quotes"],
)
async def get_daily_change(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`, `BTC-USD`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_quotes_service),
):
    # Check cache first for ultra-fast responses
    cache_key = f"daily_change:{symbol.upper()}"
    cached_data = await quote_cache.get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        change = await svc.get_daily_change_percent(symbol)
        
        # Cache the result for future requests
        await quote_cache.set(cache_key, change)
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=change, headers={"X-Cache": "MISS"})
        
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} daily change due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get(
    "/batch",
    summary="Get quotes for multiple symbols",
    description="Get current quotes for multiple symbols in a single request.",
    response_description="Map of symbol to quote data.",
    tags=["Quotes"],
)
async def get_batch_quotes(
    symbols: str = Query(..., description="Comma-separated list of symbols"),
    resp: Response = None,
    svc = Depends(get_quotes_service),
):
    """
    Batch quote endpoint for efficient multi-symbol requests.
    Optimized with parallel processing and caching.
    """
    # Parse and validate symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")
    
    if len(symbol_list) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 symbols allowed per request")
    
    # Check cache first for ultra-fast responses
    cache_key = f"batch_quotes:{','.join(sorted(symbol_list))}"
    cached_data = await quote_cache.get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service with parallel processing
    try:
        # Parallel processing for multiple symbols
        tasks = [svc.get_price_quote(symbol) for symbol in symbol_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build response with error handling
        quotes = {}
        for symbol, result in zip(symbol_list, results):
            if isinstance(result, Exception):
                logger.warning(f"Failed to fetch quote for {symbol}: {result}")
                quotes[symbol] = {"error": str(result)}
            else:
                quotes[symbol] = result.model_dump(mode='json')
        
        # Cache the result for future requests
        await quote_cache.set(cache_key, quotes)
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=quotes, headers={"X-Cache": "MISS"})
        
    except Exception as e:
        # REMOVE FALLBACK - let errors surface
        logger.error(f"Failed to get quotes for symbols {symbol_list}: {e}")
        raise

# ---- shared headers ----
def set_rate_limit_headers(resp: Response, limit: int = 60, remaining: int = 59, reset_seconds: int = 60):
    now_epoch = int(time.time())
    resp.headers["X-RateLimit-Limit"] = str(limit)
    resp.headers["X-RateLimit-Remaining"] = str(remaining)
    resp.headers["X-RateLimit-Reset"] = str(now_epoch + reset_seconds)

# ---- cache management ----
@router.delete("/cache/{symbol}", tags=["Quotes"])
async def invalidate_cache(
    symbol: str = Path(..., description="Ticker symbol to invalidate cache for"),
):
    """Invalidate cache for a specific symbol (admin/debug endpoint)"""
    symbol_upper = symbol.upper()
    
    # Invalidate specific cache keys for this symbol
    await quote_cache.delete(f"quote:{symbol_upper}")
    await quote_cache.delete(f"daily_change:{symbol_upper}")
    
    # Invalidate batch cache and other patterns using pattern deletion
    patterns_to_invalidate = [
        f"batch_quotes:*{symbol_upper}*",
        f"intelligence:{symbol_upper}:*",
        f"compare:{symbol_upper}:*"
    ]
    
    total_invalidated = 0
    for pattern in patterns_to_invalidate:
        try:
            deleted_count = await quote_cache.delete_pattern(pattern)
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
    "/{symbol}/intelligence",
    summary="Get market intelligence",
    description="Get comprehensive market intelligence including sentiment analysis, volume momentum, bid-ask imbalance, and price momentum.",
    response_description="Market intelligence data with sentiment scoring.",
    tags=["Quotes"],
)
async def get_market_intelligence(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_quotes_service),
    include_volume: bool = Query(True, description="Include volume analysis"),
    include_imbalance: bool = Query(True, description="Include bid-ask imbalance analysis"),
    include_momentum: bool = Query(True, description="Include price momentum analysis"),
):
    """
    Get comprehensive market intelligence for real-time trading decisions.
    
    **Sentiment Analysis:**
    - **Volume Analysis**: Current vs average volume momentum
    - **Market Imbalance**: Bid vs ask size imbalance
    - **Price Momentum**: Price change and intraday movement
    
    **Sentiment Scoring:**
    - **Score Range**: -3 to +3 (bearish to bullish)
    - **Confidence**: High (score ≥2) or Medium (score <2)
    - **Factors**: Specific reasons for sentiment (e.g., "high_volume", "bid_heavy")
    
    **Use Cases:**
    - Real-time sentiment monitoring
    - Entry/exit timing
    - Market structure analysis
    - Risk assessment
    """
    # Check cache first for ultra-fast responses
    cache_key = f"intelligence:{symbol.upper()}:{include_volume}:{include_imbalance}:{include_momentum}"
    cached_data = await quote_cache.get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        # Get market intelligence
        result = await svc.get_market_intelligence(
            symbol=symbol,
            include_volume=include_volume,
            include_imbalance=include_imbalance,
            include_momentum=include_momentum
        )
        
        # Ensure result is JSON serializable by converting datetime objects
        serializable_result = _make_json_serializable(result)
        
        # Cache the serializable result for future requests (shorter TTL for real-time data)
        await quote_cache.set(cache_key, serializable_result, ttl_seconds=10)  # 10 seconds for real-time data
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=serializable_result, headers={"X-Cache": "MISS"})
        
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} intelligence due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get(
    "/{symbol}/compare",
    summary="Get comparative analysis",
    description="Compare a symbol's performance against market benchmarks and indices.",
    response_description="Comparative analysis vs benchmarks with performance metrics.",
    tags=["Quotes"],
)
async def get_comparative_analysis(
    symbol: str = Path(..., description="Ticker symbol to analyze (e.g., `AAPL`, `TSLA`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_quotes_service),
    benchmarks: str = Query(
        "SPY,QQQ,IWM",
        description="Comma-separated list of benchmark symbols.",
        examples={
            "default": {"summary": "Major indices", "value": "SPY,QQQ,IWM"},
            "tech": {"summary": "Tech focus", "value": "QQQ,SOXX,XLK"},
            "broad": {"summary": "Broad market", "value": "SPY,VTI,VT"},
        },
    ),
    metrics: str = Query(
        "price_change,relative_strength,volatility",
        description="Comma-separated list of metrics to compare.",
        examples={
            "default": {"summary": "All metrics", "value": "price_change,relative_strength,volatility"},
            "performance": {"summary": "Performance only", "value": "price_change,relative_strength"},
            "risk": {"summary": "Risk metrics", "value": "volatility"},
        },
    ),
    timeframe: str = Query(
        "ytd",
        description="Time period for comparison.",
        examples={
            "ytd": {"summary": "Year-to-Date (default)", "value": "ytd"},
            "quarterly": {"summary": "Last 3 months", "value": "quarterly"},
            "monthly": {"summary": "Last 30 days", "value": "monthly"},
        },
    ),
):
    """
    Compare a symbol's performance against market benchmarks.
    
    **Available Metrics:**
    - **price_change**: Period % change comparison
    - **relative_strength**: Price ratio vs benchmarks
    - **volatility**: Risk comparison (placeholder)
    
    **Available Timeframes:**
    - **ytd**: Year-to-Date (January 1st to present)
    - **quarterly**: Last 3 months (90 days)
    - **monthly**: Last 30 days
    
    **Default Benchmarks:**
    - **SPY**: S&P 500 ETF (large cap)
    - **QQQ**: Nasdaq-100 ETF (tech)
    - **IWM**: Russell 2000 ETF (small cap)
    
    **Use Cases:**
    - Sector rotation analysis
    - Relative strength trading
    - Risk-adjusted performance
    - Market timing decisions
    """
    # Check cache first for ultra-fast responses
    cache_key = f"compare:{symbol.upper()}:{benchmarks}:{metrics}:{timeframe}"
    cached_data = await quote_cache.get(cache_key)
    if cached_data:
        set_rate_limit_headers(resp)
        return JSONResponse(content=cached_data, headers={"X-Cache": "HIT"})
    
    # Cache miss - fetch from service
    try:
        # Parse parameters
        benchmark_list = [b.strip().upper() for b in benchmarks.split(",") if b.strip()]
        metric_list = [m.strip().lower() for m in metrics.split(",") if m.strip()]
        
        # Validate metrics
        valid_metrics = {"price_change", "relative_strength", "correlation", "volatility"}
        invalid_metrics = set(metric_list) - valid_metrics
        if invalid_metrics:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid metrics: {', '.join(invalid_metrics)}. Valid options: {', '.join(valid_metrics)}"
            )
        
        # Validate timeframe
        valid_timeframes = {"ytd", "quarterly", "monthly"}
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe '{timeframe}'. Valid options: {', '.join(valid_timeframes)}"
            )
        
        # Get comparative analysis
        result = await svc.get_comparative_analysis(
            symbol=symbol,
            benchmarks=benchmark_list,
            metrics=metric_list,
            timeframe=timeframe
        )
        
        # Ensure result is JSON serializable by converting datetime objects
        serializable_result = _make_json_serializable(result)
        
        # Cache the serializable result for future requests
        await quote_cache.set(cache_key, serializable_result, ttl_seconds=30)  # 30 seconds for comparative data
        
        set_rate_limit_headers(resp)
        return JSONResponse(content=serializable_result, headers={"X-Cache": "MISS"})
        
    except HTTPException:
        raise
    except Exception as e:
        # Return cached data if available, even if expired
        if cached_data:
            logger.warning(f"Using expired cache for {symbol} comparison due to error: {e}")
            set_rate_limit_headers(resp)
            return JSONResponse(content=cached_data, headers={"X-Cache": "EXPIRED"})
        raise

@router.get("/cache/status", tags=["Quotes"])
async def get_cache_status():
    """Get cache statistics and status"""
    cache = quote_cache
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
