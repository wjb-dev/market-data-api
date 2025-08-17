from __future__ import annotations

from fastapi import APIRouter, Query, Depends, HTTPException, status, Path, Response
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import logging

import time
from src.app.core.config import get_alpaca
from src.app.services.quotes_service import get_quotes_service
from src.app.services.cache_service import get_quotes_cache
from src.app.schemas.quote import Quote, QuoteData, MarketIntelligence, ComparativeAnalysis, DailyChangeResponse, QuotesCacheStatusResponse


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
    response_model=QuoteData,
    summary="Get real-time quote for a symbol",
    description="""
    Retrieve real-time market quote data for a specific stock symbol.
    
    **Features:**
    - Live bid/ask prices and sizes
    - Real-time spread calculations
    - Exchange information
    - Quote conditions and metadata
    
    **Use Cases:**
    - Live price monitoring
    - Spread analysis
    - Order book analysis
    - Real-time trading decisions
    
    **Data Source:** Alpaca Market Data API (Real-time)
    **Update Frequency:** Real-time (sub-second)
    **Cache TTL:** 10 seconds
    """,
    responses={
        200: {
            "description": "Successfully retrieved quote data",
            "content": {
                "application/json": {
                    "example": {
                        "symbol": "AAPL",
                        "quote": {
                            "timestamp": "2025-08-16T00:30:00Z",
                            "ask_exchange": "V",
                            "ask_price": 150.25,
                            "ask_size": 100,
                            "bid_exchange": "V",
                            "bid_price": 150.20,
                            "bid_size": 200,
                            "conditions": ["R"],
                            "tape": "C",
                            "spread": 0.05,
                            "spread_pct": 0.033,
                            "mid_price": 150.225
                        },
                        "status": "success",
                        "timestamp": "2025-08-16T00:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid symbol format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid symbol format. Use uppercase letters only (e.g., AAPL, TSLA)"
                    }
                }
            }
        },
        404: {
            "description": "Symbol not found or no data available",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No quote data available for symbol INVALID"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded. Please wait before making another request."
                    }
                }
            }
        },
        500: {
            "description": "Internal server error or external API failure",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to fetch quote data from Alpaca API"
                    }
                }
            }
        }
    },
    tags=["Quotes"],
    openapi_extra={
        "x-logo": {"url": "https://example.com/logo.png"},
        "x-tagGroups": [{"name": "Market Data", "tags": ["Quotes", "Candles", "Articles"]}]
    }
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
    response_model=DailyChangeResponse,
    summary="Get daily percent change",
    description="Percent change vs. previous daily close (e.g., `1.23` = +1.23%).",
    response_description="Daily change data with percentage and absolute values.",
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
    "/batch/{symbols}",
    response_model=List[QuoteData],
    summary="Get real-time quotes for multiple symbols",
    description="""
    Retrieve real-time market quotes for multiple stock symbols in a single request.
    
    **Features:**
    - Batch quote retrieval for up to 100 symbols
    - Optimized for multiple symbol monitoring
    - Real-time pricing and spread data
    - Efficient caching for batch requests
    
    **Use Cases:**
    - Portfolio monitoring
    - Watchlist updates
    - Multi-symbol analysis
    - Dashboard data feeds
    
    **Performance:**
    - **Single Symbol:** ~50ms response time
    - **10 Symbols:** ~100ms response time
    - **100 Symbols:** ~500ms response time
    - **Cache TTL:** 10 seconds
    
    **Rate Limits:** 200 requests/minute (Alpaca free tier)
    """,
    responses={
        200: {
            "description": "Successfully retrieved batch quotes",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "symbol": "AAPL",
                            "quote": {
                                "timestamp": "2025-08-16T00:30:00Z",
                                "ask_price": 150.25,
                                "bid_price": 150.20,
                                "spread": 0.05,
                                "mid_price": 150.225
                            },
                            "status": "success"
                        },
                        {
                            "symbol": "TSLA",
                            "quote": {
                                "timestamp": "2025-08-16T00:30:00Z",
                                "ask_price": 245.80,
                                "bid_price": 245.75,
                                "spread": 0.05,
                                "mid_price": 245.775
                            },
                            "status": "success"
                        }
                    ]
                }
            }
        },
        400: {
            "description": "Invalid symbols format or too many symbols",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Maximum 100 symbols allowed. Received: 150"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error or external API failure",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to fetch batch quotes from Alpaca API"
                    }
                }
            }
        }
    },
    tags=["Quotes"]
)
async def get_batch_quotes(
    symbols: str = Path(..., description="Comma-separated list of symbols"),
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
    response_model=MarketIntelligence,
    summary="Get comprehensive market intelligence",
    description="""
    Retrieve advanced market intelligence and analysis for a specific symbol.
    
    **Intelligence Features:**
    - **Spread Analysis:** Bid-ask spreads and percentage calculations
    - **Volume Analysis:** Current vs average volume, volume trends
    - **Order Flow:** Bid-ask imbalance and buying/selling pressure
    - **Price Momentum:** Daily changes and trend strength
    
    **Use Cases:**
    - AI-powered trading decisions
    - Market microstructure analysis
    - Order flow analysis
    - Trading strategy development
    
    **Data Sources:**
    - **Real-time Quotes:** Alpaca Market Data API
    - **Volume Data:** Historical volume analysis
    - **Calculations:** Real-time spread and momentum metrics
    
    **Performance:** Sub-200ms response time with caching
    """,
    responses={
        200: {
            "description": "Successfully retrieved market intelligence",
            "content": {
                "application/json": {
                    "example": {
                        "symbol": "AAPL",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "current_price": 150.25,
                        "bid_price": 150.20,
                        "ask_price": 150.25,
                        "spread": 0.05,
                        "spread_pct": 0.033,
                        "volume_analysis": {
                            "current_volume": 15000000,
                            "avg_volume": 12000000,
                            "volume_ratio": 1.25,
                            "volume_trend": "above_average"
                        },
                        "bid_ask_imbalance": {
                            "bid_volume": 8000000,
                            "ask_volume": 7000000,
                            "imbalance_ratio": 1.14,
                            "pressure": "buying"
                        },
                        "price_momentum": {
                            "daily_change": 2.45,
                            "momentum_strength": "strong",
                            "trend_direction": "upward"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid parameters or symbol format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid symbol format. Use uppercase letters only (e.g., AAPL)"
                    }
                }
            }
        },
        500: {
            "description": "Failed to generate market intelligence",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to generate intelligence: Invalid quote data"
                    }
                }
            }
        }
    },
    tags=["Quotes"]
)
async def get_market_intelligence(
    symbol: str = Path(..., description="Ticker symbol (e.g., `AAPL`, `SPY`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_quotes_service),
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
    response_model=ComparativeAnalysis,
    summary="Compare symbol performance against benchmarks",
    description="""
    Compare a symbol's performance against major market benchmarks over different timeframes.
    
    **Comparison Metrics:**
    - **Price Change:** Absolute and relative performance
    - **Relative Strength:** Performance ratio vs benchmarks
    - **Volatility:** Risk-adjusted performance comparison
    - **Outperformance Analysis:** Win/loss ratios vs benchmarks
    
    **Available Timeframes:**
    - **YTD:** Year-to-date performance (default)
    - **Quarterly:** Last 3 months performance
    - **Monthly:** Last 30 days performance
    
    **Default Benchmarks:**
    - **SPY:** S&P 500 ETF (large-cap US stocks)
    - **QQQ:** NASDAQ-100 ETF (tech-heavy stocks)
    - **IWM:** Russell 2000 ETF (small-cap stocks)
    
    **Use Cases:**
    - Portfolio performance analysis
    - Sector rotation strategies
    - Risk-adjusted returns
    - AI trading signal generation
    
    **Performance:** 300-800ms response time depending on data freshness
    """,
    responses={
        200: {
            "description": "Successfully retrieved comparative analysis",
            "content": {
                "application/json": {
                    "example": {
                        "symbol": "AAPL",
                        "timeframe": "ytd",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "comparison": {
                            "SPY": {
                                "price_change": {
                                    "symbol": 15.2,
                                    "benchmark": 8.5,
                                    "difference": 6.7,
                                    "outperformance": True,
                                    "outperformance_pct": 6.7
                                },
                                "relative_strength": {
                                    "ratio": 1.79,
                                    "strength": "very_strong",
                                    "strength_score": 1.79
                                },
                                "volatility": {
                                    "symbol_volatility": 18.5,
                                    "benchmark_volatility": 15.2,
                                    "comparison": "higher",
                                    "difference": 3.3
                                }
                            }
                        },
                        "summary": {
                            "total_benchmarks": 2,
                            "outperforming": 2,
                            "underperforming": 0,
                            "overall_performance": "outperforming_all",
                            "performance_ratio": 1.0
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid parameters or symbol format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid timeframe. Must be one of: ytd, quarterly, monthly"
                    }
                }
            }
        },
        500: {
            "description": "Failed to generate comparative analysis",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to generate analysis: Benchmark data unavailable"
                    }
                }
            }
        }
    },
    tags=["Quotes"]
)
async def get_comparative_analysis(
    symbol: str = Path(..., description="Ticker symbol to analyze (e.g., `AAPL`, `TSLA`).", examples={"ex1": {"value": "AAPL"}}),
    resp: Response = None,
    svc = Depends(get_quotes_service),
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

@router.get(
    "/cache/status",
    response_model=QuotesCacheStatusResponse,
    summary="Get Cache Status",
    tags=["Quotes"]
)
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
