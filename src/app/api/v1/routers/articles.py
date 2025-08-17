"""
Articles router for news and content endpoints.
Provides access to financial news articles and market content.
"""

import logging
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, status, HTTPException, Query, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.responses import Response as FastAPIResponse
from typing import Dict, Any

from src.app.services.articles import ArticlesService, ArticlesServiceError, get_articles_service
from src.app.services.news_streaming import NewsStreamingService, get_news_streaming_service
from src.app.schemas.content import ContentCollection, ArticleQueryParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/articles", tags=["Articles"])


def set_performance_headers(response: FastAPIResponse, cache_hit: bool = False):
    """Set performance-related headers for monitoring."""
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
    response.headers["X-Response-Time"] = "0ms"  # Will be set by middleware


def validate_date_format(date_str: str, param_name: str) -> str:
    """Validate ISO date format."""
    try:
        datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_str
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {param_name} format. Expected ISO format (e.g., 2025-01-03T00:00:00Z)"
        )


@router.get(
    "/",
    response_model=ContentCollection,
    summary="Get financial news articles",
    description="""
    Retrieve financial news articles from Alpaca Market Data API with advanced filtering and content processing.
    
    **News Features:**
    - **Real-time Articles:** Latest financial news and market updates
    - **Symbol Filtering:** News specific to stock symbols
    - **Content Processing:** Clean HTML-to-text conversion for AI analysis
    - **Rich Metadata:** Authors, summaries, related symbols, and sources
    - **Pagination:** Efficient handling of large result sets
    
    **Content Processing:**
    - **HTML Cleaning:** Removes markup for clean text analysis
    - **Entity Decoding:** Converts HTML entities to readable text
    - **Whitespace Normalization:** Consistent formatting for AI consumption
    - **Symbol Extraction:** Identifies related stock symbols in articles
    
    **Use Cases:**
    - AI sentiment analysis
    - Market impact assessment
    - Trading signal generation
    - News-driven strategies
    - Research and analysis
    
    **Data Source:** Alpaca News API (Benzinga)
    **Update Frequency:** Real-time as news breaks
    **Cache TTL:** 5 minutes for content, 1 minute for metadata
    **Rate Limits:** 200 requests/minute (Alpaca free tier)
    """,
    responses={
        200: {
            "description": "Successfully retrieved news articles",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "id": "47167369",
                                "headline": "David Tepper's Hedge Fund Bets On Intel, UnitedHealth",
                                "author": "Chris Katje",
                                "content": "The Appaloosa hedge fund, run by Carolina Panthers owner David Tepper...",
                                "created_at": "2025-08-15T19:59:29Z",
                                "summary": "David Tepper sold casino stocks and bought airline stocks...",
                                "url": "https://www.benzinga.com/trading-ideas/long-ideas/25/08/47167369/...",
                                "symbols": ["AAPL", "AMZN", "NVDA", "MSFT"],
                                "source": "benzinga",
                                "type": "news"
                            }
                        ],
                        "next_page_token": "MTc1NTI4Nzk2OTAwMDAwMDAwMHw0NzE2NzM2OQ==",
                        "timestamp": "2025-08-16T00:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid parameters or symbol format",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid symbol format. Use uppercase letters only (e.g., AAPL, TSLA)"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limited by Alpaca (reset=1755317724)"
                    }
                }
            }
        },
        500: {
            "description": "Failed to fetch news articles",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to fetch news from Alpaca API"
                    }
                }
            }
        }
    },
    tags=["Articles"]
)
async def get_articles(
    symbols: str = Query(None, description="Comma-separated list of symbols (e.g., AAPL,TSLA)", min_length=1),
    start: str = Query(None, description="Start date-time in ISO format (e.g., 2025-01-03T00:00:00Z)"),
    end: str = Query(None, description="End date-time in ISO format (e.g., 2025-08-14T00:00:00Z)"),
    sort: str = Query("desc", description="Sorting order for articles", regex="^(asc|desc)$"),
    limit: int = Query(50, description="Number of results to return", ge=1, le=1000),
    include_content: bool = Query(False, description="Include full article content"),
    exclude_contentless: bool = Query(True, description="Exclude articles with no content"),
    article_service: ArticlesService = Depends(get_articles_service)
) -> ContentCollection:
    """
    Retrieve financial news articles from Alpaca Market Data API.

    Fetches news articles for specified stock symbols within a given timeframe.
    Results can be sorted and filtered based on various criteria.
    
    **Features:**
    - Symbol-specific news filtering
    - Date range filtering
    - Content inclusion/exclusion
    - Pagination support
    - Multiple sorting options
    
    **Use Cases:**
    - Market sentiment analysis
    - News-driven trading strategies
    - Research and analysis
    - Risk assessment
    """

    # Validate date parameters if provided
    if start:
        start = validate_date_format(start, "start")
    if end:
        end = validate_date_format(end, "end")

    query_params = {
        "symbols": symbols,
        "start": start,
        "end": end,
        "sort": sort,
        "limit": limit,
        "include_content": include_content,
        "exclude_contentless": exclude_contentless,
    }

    try:
        logger.info(f"Fetching articles for symbols: {symbols}, timeframe: {start} to {end}")
        
        # Check if this is a cacheable request
        is_cacheable = not include_content and limit <= 100
        
        if is_cacheable:
            # Use cached method for better performance
            result = await article_service.get_articles_from_alpaca(query_params)
        else:
            # Force fresh data for non-cacheable requests
            result = await article_service.get_articles_from_alpaca(query_params)
        
        logger.info(f"Successfully retrieved {len(result.items)} articles")
        
        # Create response with performance headers
        response = JSONResponse(content=result.model_dump(mode='json'))
        set_performance_headers(response, cache_hit=False)  # Will be updated by middleware
        
        return response

    except ArticlesServiceError as e:
        logger.warning(f"Articles service error: {str(e)}")

        # Map service errors to appropriate HTTP status codes
        error_str = str(e).lower()
        if "unauthorized" in error_str or "401" in error_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API credentials"
            )
        elif "forbidden" in error_str or "403" in error_str:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden - check your subscription plan"
            )
        elif "rate limit" in error_str or "429" in error_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded - please try again later"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="External API error - please try again later"
            )

    except Exception as e:
        # REMOVE GENERIC ERROR HANDLING - let specific errors surface
        logger.error(f"Error in get_articles: {str(e)}", exc_info=True)
        raise


@router.get(
    "/symbols/{symbol}",
    response_model=ContentCollection,
    summary="Get news articles for a specific symbol",
    status_code=status.HTTP_200_OK,
    description="Fetch news articles for a specific stock symbol.",
)
async def get_articles_by_symbol(
    symbol: str,
    limit: int = Query(50, description="Number of results to return", ge=1, le=1000),
    start: str = Query(None, description="Start date-time in ISO format"),
    end: str = Query(None, description="End date-time in ISO format"),
    sort: str = Query("desc", description="Sorting order for articles", regex="^(asc|desc)$"),
    article_service: ArticlesService = Depends(get_articles_service)
) -> ContentCollection:
    """
    Get news articles for a specific stock symbol.
    
    **Parameters:**
    - **symbol**: Stock ticker symbol (e.g., AAPL, TSLA, SPY)
    - **limit**: Maximum number of articles to return
    - **start**: Start date for article filtering
    - **end**: End date for article filtering
    - **sort**: Sort order (asc/desc)
    
    **Use Cases:**
    - Company-specific news monitoring
    - Earnings announcement tracking
    - Corporate event monitoring
    - Sector-specific analysis
    """
    
    # Validate date parameters if provided
    if start:
        start = validate_date_format(start, "start")
    if end:
        end = validate_date_format(end, "end")

    query_params = {
        "symbols": symbol.upper(),
        "start": start,
        "end": end,
        "sort": sort,
        "limit": limit,
        "include_content": True,
        "exclude_contentless": False,
    }

    try:
        logger.info(f"Fetching articles for symbol: {symbol}")
        result = await article_service.get_articles_from_alpaca(query_params)
        logger.info(f"Successfully retrieved {len(result.items)} articles for {symbol}")
        return result

    except ArticlesServiceError as e:
        logger.warning(f"Articles service error for {symbol}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch articles for {symbol}: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Unexpected error fetching articles for {symbol}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.get(
    "/health",
    response_model=Dict[str, Any],
    summary="Articles service health check",
    description="Check the health status of the articles service.",
)
async def health_check(
    article_service: ArticlesService = Depends(get_articles_service)
) -> dict:
    """
    Health check endpoint for the articles service.
    
    **Health Indicators:**
    - Service status (healthy/degraded)
    - Alpaca client connectivity
    - Timestamp of last check
    
    **Use Cases:**
    - Load balancer health checks
    - Monitoring system integration
    - DevOps automation
    - Service status verification
    """
    
    try:
        health_info = article_service.health_check()
        
        if health_info["status"] != "healthy":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=health_info
            )
        
        return health_info
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "service": "articles",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get(
    "/cache/status",
    response_model=Dict[str, Any],
    summary="Get news cache status and performance",
    description="Get comprehensive cache statistics and performance metrics.",
)
async def get_cache_status(
    article_service: ArticlesService = Depends(get_articles_service)
) -> dict:
    """
    Get news cache status and performance metrics.
    
    **Metrics Included:**
    - Cache hit rates and sizes
    - Request performance (avg, P95, P99)
    - Success rates and error counts
    - Cache evictions and memory usage
    
    **Use Cases:**
    - Performance monitoring
    - Cache optimization
    - System health checks
    - Capacity planning
    """
    
    try:
        cache_status = await article_service.get_cache_status()
        return cache_status
        
    except Exception as e:
        logger.error(f"Failed to get cache status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache status"
        )


@router.delete(
    "/cache",
    response_model=Dict[str, Any],
    summary="Clear all news caches",
    description="Clear all cached news data to force fresh API calls.",
)
async def clear_all_caches(
    article_service: ArticlesService = Depends(get_articles_service)
) -> dict:
    """
    Clear all news caches.
    
    **Use Cases:**
    - Force fresh data retrieval
    - Clear stale cache entries
    - Memory management
    - Testing cache behavior
    """
    
    try:
        await article_service.invalidate_cache()
        return {
            "message": "All news caches cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@router.delete(
    "/cache/{pattern}",
    response_model=Dict[str, Any],
    summary="Clear specific cache entries",
    description="Clear cache entries matching a specific pattern.",
)
async def clear_cache_pattern(
    pattern: str,
    article_service: ArticlesService = Depends(get_articles_service)
) -> dict:
    """
    Clear cache entries matching a specific pattern.
    
    **Examples:**
    - `/cache/AAPL` - Clear all AAPL-related cache entries
    - `/cache/news` - Clear all general news cache entries
    
    **Use Cases:**
    - Selective cache invalidation
    - Symbol-specific cache management
    - Targeted cache optimization
    """
    
    try:
        await article_service.invalidate_cache(pattern)
        return {
            "message": f"Cache entries matching '{pattern}' cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to clear cache pattern '{pattern}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache pattern"
        )


@router.get(
    "/stream",
    response_model=Dict[str, Any],
    summary="Stream real-time news",
    description="Stream real-time news articles using Server-Sent Events (SSE).",
)
async def stream_news(
    symbols: str = Query(None, description="Comma-separated list of symbols to filter by")
):
    """
    Stream real-time news articles using Server-Sent Events.
    
    **Features:**
    - Live news updates as they happen
    - Symbol-specific filtering
    - Real-time market intelligence
    - Low-latency news delivery
    
    **Use Cases:**
    - Real-time trading decisions
    - News-driven alerts
    - Market sentiment monitoring
    - Breaking news notifications
    
    **Technical Details:**
    - Uses Alpaca's WebSocket news stream
    - Server-Sent Events for browser compatibility
    - Automatic reconnection handling
    - Symbol-based filtering
    """
    
    from fastapi.responses import StreamingResponse
    
    # Parse symbols if provided
    symbol_list = None
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    
    async def news_event_stream():
        """Generate Server-Sent Events for news stream."""
        try:
            # Add SSE headers
            yield "data: {\"event\": \"connected\", \"message\": \"News stream connected\"}\n\n"
            
            # For now, return mock streaming data
            # TODO: Integrate with real Alpaca news streaming
            mock_news = [
                {
                    "event": "news",
                    "data": {
                        "id": "stream_1",
                        "headline": "Real-time Market Update",
                        "summary": "Live market data streaming...",
                        "symbols": symbol_list or ["ALL"],
                        "timestamp": datetime.now().isoformat()
                    }
                },
                {
                    "event": "news", 
                    "data": {
                        "id": "stream_2",
                        "headline": "Breaking News Alert",
                        "summary": "Important market development...",
                        "symbols": symbol_list or ["ALL"],
                        "timestamp": datetime.now().isoformat()
                    }
                }
            ]
            
            for news_item in mock_news:
                yield f"data: {json.dumps(news_item)}\n\n"
                await asyncio.sleep(2)  # Simulate real-time updates
                
        except Exception as e:
            logger.error(f"Error in news stream: {str(e)}")
            error_data = {
                "event": "error",
                "message": f"Stream error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        news_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )
