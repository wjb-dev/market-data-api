from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any
from src.app.core.http_client import get_http_client
from src.app.services.cache_service import get_candles_cache, get_quotes_cache, get_news_cache
from src.app.core.redis_service import get_redis_service
from src.app.schemas.performance import PerformanceOverview, HTTPClientMetrics, CacheMetrics, RedisMetrics

router = APIRouter(prefix="/performance", tags=["Performance"])

@router.get(
    "/http-client",
    response_model=HTTPClientMetrics,
    summary="Get HTTP client performance metrics",
    description="Performance statistics for the optimized HTTP client including response times and success rates."
)
async def get_http_client_metrics() -> HTTPClientMetrics:
    """Get HTTP client performance metrics."""
    try:
        http_client = get_http_client()
        stats = http_client.get_performance_stats()
        return HTTPClientMetrics(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get HTTP client metrics: {str(e)}"
        )

@router.get(
    "/caches",
    response_model=CacheMetrics,
    summary="Get all cache performance metrics",
    description="Performance statistics for all cache layers including Redis and memory fallbacks."
)
async def get_cache_metrics() -> CacheMetrics:
    """Get cache performance metrics for all cache types."""
    try:
        candles_cache = get_candles_cache()
        quotes_cache = get_quotes_cache()
        news_cache = get_news_cache()
        
        return CacheMetrics(
            candles=candles_cache.get_stats(),
            quotes=quotes_cache.get_stats(),
            news=news_cache.get_stats()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cache metrics: {str(e)}"
        )

@router.get(
    "/redis",
    response_model=RedisMetrics,
    summary="Get Redis performance metrics",
    description="Redis server performance statistics and health status."
)
async def get_redis_metrics() -> RedisMetrics:
    """Get Redis performance metrics."""
    try:
        redis_service = await get_redis_service()
        stats = await redis_service.get_stats()
        return RedisMetrics(**stats)
    except Exception as e:
        return RedisMetrics(
            connected=False,
            memory_usage="N/A",
            operations_per_second=0,
            connected_clients=0,
            uptime_seconds=0,
            error=str(e)
        )

@router.get(
    "/overview",
    response_model=PerformanceOverview,
    summary="Get comprehensive performance overview",
    description="""
    Retrieve complete system performance metrics including HTTP client, cache performance, and Redis statistics.
    
    **Performance Metrics:**
    - **HTTP Client:** Response times, success rates, error tracking
    - **Cache Performance:** Hit rates, sizes, eviction statistics
    - **Redis Health:** Connection status, memory usage, operations/sec
    - **System Overview:** Uptime, total requests, performance trends
    
    **Key Performance Indicators:**
    - **Response Time:** Average, P95, P99 latency measurements
    - **Cache Efficiency:** Hit rates and memory utilization
    - **Error Rates:** Success/failure ratios and error categorization
    - **Throughput:** Requests per second and concurrent connections
    
    **Use Cases:**
    - System health monitoring
    - Performance optimization
    - Capacity planning
    - SLA monitoring
    - DevOps automation
    
    **Data Freshness:** Real-time metrics with 1-minute aggregation
    **Historical Data:** Last 24 hours of performance trends
    **Alert Thresholds:** Configurable performance alerts
    """,
    responses={
        200: {
            "description": "Successfully retrieved performance overview",
            "content": {
                "application/json": {
                    "example": {
                        "service": "performance_overview",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "http_client": {
                            "total_requests": 15000,
                            "success_rate": 98.5,
                            "avg_response_time": 0.125,
                            "p95_response_time": 0.450,
                            "p99_response_time": 0.850,
                            "error_rate": 1.5,
                            "requests_per_second": 25.3
                        },
                        "caches": {
                            "candles": {
                                "hit_rate_percent": 82.3,
                                "cache_size": 150,
                                "memory_usage": "45.2MB",
                                "evictions": 12
                            },
                            "quotes": {
                                "hit_rate_percent": 78.4,
                                "cache_size": 200,
                                "memory_usage": "62.8MB",
                                "evictions": 8
                            },
                            "news": {
                                "hit_rate_percent": 91.2,
                                "cache_size": 75,
                                "memory_usage": "28.1MB",
                                "evictions": 3
                            }
                        },
                        "redis": {
                            "connected": True,
                            "memory_usage": "45.2MB",
                            "operations_per_second": 1250,
                            "connected_clients": 15,
                            "uptime_seconds": 86400
                        },
                        "system": {
                            "uptime_seconds": 86400,
                            "total_requests": 15000,
                            "active_connections": 25,
                            "memory_usage": "256MB",
                            "cpu_usage_percent": 12.5
                        }
                    }
                }
            }
        },
        500: {
            "description": "Failed to retrieve performance metrics",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to collect performance metrics"
                    }
                }
            }
        }
    },
    tags=["Performance"]
)
async def get_performance_overview() -> PerformanceOverview:
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
        
        return PerformanceOverview(
            service="performance_overview",
            timestamp="2024-01-01T00:00:00Z",  # Will be set by middleware
            performance_score=round(performance_score, 2),
            http_client=HTTPClientMetrics(**http_stats),
            caches=CacheMetrics(**cache_stats),
            redis=RedisMetrics(**redis_stats),
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get performance overview: {str(e)}"
        )

@router.delete(
    "/caches/clear",
    response_model=Dict[str, Any],
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
