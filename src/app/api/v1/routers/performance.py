from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
from src.app.core.http_client import get_http_client
from src.app.services.cache_service import get_candles_cache, get_quotes_cache, get_news_cache
from src.app.core.redis_service import get_redis_service

router = APIRouter(prefix="/performance", tags=["Performance"])

@router.get(
    "/http-client",
    summary="Get HTTP client performance metrics",
    description="Performance statistics for the optimized HTTP client including response times and success rates."
)
async def get_http_client_metrics() -> Dict[str, Any]:
    """Get HTTP client performance metrics."""
    try:
        http_client = get_http_client()
        stats = http_client.get_performance_stats()
        return {
            "service": "http_client",
            "metrics": stats,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get HTTP client metrics: {str(e)}"
        )

@router.get(
    "/caches",
    summary="Get all cache performance metrics",
    description="Performance statistics for all cache layers including Redis and memory fallbacks."
)
async def get_cache_metrics() -> Dict[str, Any]:
    """Get cache performance metrics for all cache types."""
    try:
        candles_cache = get_candles_cache()
        quotes_cache = get_quotes_cache()
        news_cache = get_news_cache()
        
        return {
            "service": "cache_system",
            "caches": {
                "candles": candles_cache.get_stats(),
                "quotes": quotes_cache.get_stats(),
                "news": news_cache.get_stats()
            },
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache metrics: {str(e)}"
        )

@router.get(
    "/redis",
    summary="Get Redis performance metrics",
    description="Redis server performance statistics and health status."
)
async def get_redis_metrics() -> Dict[str, Any]:
    """Get Redis performance metrics."""
    try:
        redis_service = await get_redis_service()
        stats = await redis_service.get_stats()
        return {
            "service": "redis",
            "metrics": stats,
            "status": "success"
        }
    except Exception as e:
        return {
            "service": "redis",
            "metrics": {},
            "status": "error",
            "error": str(e)
        }

@router.get(
    "/overview",
    summary="Get comprehensive performance overview",
    description="Complete performance overview including HTTP client, caches, and Redis metrics."
)
async def get_performance_overview() -> Dict[str, Any]:
    """Get comprehensive performance overview."""
    try:
        # HTTP Client metrics
        http_client = get_http_client()
        http_stats = http_client.get_performance_stats()
        
        # Cache metrics
        candles_cache = get_candles_cache()
        quotes_cache = get_quotes_cache()
        news_cache = get_news_cache()
        
        cache_stats = {
            "candles": candles_cache.get_stats(),
            "quotes": quotes_cache.get_stats(),
            "news": news_cache.get_stats()
        }
        
        # Redis metrics (if available)
        try:
            redis_service = await get_redis_service()
            redis_stats = await redis_service.get_stats()
            redis_status = "connected"
        except Exception:
            redis_stats = {}
            redis_status = "disconnected"
        
        # Calculate overall performance score
        total_requests = http_stats.get("total_requests", 0)
        success_rate = http_stats.get("success_rate_percent", 0)
        avg_response_time = http_stats.get("avg_response_time_ms", 0)
        
        # Performance scoring (0-100)
        if total_requests == 0:
            performance_score = 0
        else:
            # Success rate weight: 40%, Response time weight: 30%, Cache hit rate weight: 30%
            success_score = min(success_rate, 100)
            response_score = max(0, 100 - (avg_response_time / 10))  # Penalize high response times
            cache_hit_score = sum(cache.get("cache_hit_rate_percent", 0) for cache in cache_stats.values()) / len(cache_stats)
            
            performance_score = (success_score * 0.4) + (response_score * 0.3) + (cache_hit_score * 0.3)
        
        return {
            "service": "performance_overview",
            "timestamp": "2024-01-01T00:00:00Z",  # Will be set by middleware
            "performance_score": round(performance_score, 2),
            "http_client": {
                "status": "operational",
                "metrics": http_stats
            },
            "caches": {
                "status": "operational",
                "metrics": cache_stats
            },
            "redis": {
                "status": redis_status,
                "metrics": redis_stats
            },
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance overview: {str(e)}"
        )

@router.delete(
    "/caches/clear",
    summary="Clear all caches",
    description="Clear all cache layers including Redis and memory caches."
)
async def clear_all_caches() -> Dict[str, Any]:
    """Clear all caches."""
    try:
        candles_cache = get_candles_cache()
        quotes_cache = get_quotes_cache()
        news_cache = get_news_cache()
        
        candles_cleared = await candles_cache.clear()
        quotes_cleared = await quotes_cache.clear()
        news_cleared = await news_cache.clear()
        
        total_cleared = candles_cleared + quotes_cleared + news_cleared
        
        return {
            "service": "cache_clear",
            "message": f"Cleared {total_cleared} cache entries",
            "details": {
                "candles_cleared": candles_cleared,
                "quotes_cleared": quotes_cleared,
                "news_cleared": news_cleared
            },
            "status": "success"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear caches: {str(e)}"
        )
