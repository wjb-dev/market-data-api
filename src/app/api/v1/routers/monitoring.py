"""
Monitoring and performance metrics endpoints for the Market Data API.
Provides real-time insights into API performance, cache efficiency, and system health.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
import time
import logging
from typing import Dict, Any

from src.app.core.monitoring import get_performance_monitor, record_request_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get(
    "/health",
    summary="System Health Check",
    description="Get overall system health status with detailed health checks.",
    response_description="System health status and individual health check results.",
)
async def get_health_status():
    """
    Get comprehensive system health status.
    
    **Health Checks:**
    - **API Responsive**: Basic API availability
    - **Cache Healthy**: Cache hit rates above 50%
    - **Response Time Healthy**: Average response time under 1 second
    - **Error Rate Healthy**: Error rate below 5%
    
    **Use Cases:**
    - Load balancer health checks
    - Monitoring system integration
    - DevOps automation
    - User confidence verification
    """
    try:
        monitor = get_performance_monitor()
        health_status = await monitor.get_health_status()
        
        # Record this health check request
        await record_request_metrics(
            endpoint="/monitoring/health",
            method="GET",
            status_code=200,
            response_time=0.0,  # Health check is fast
            cache_hit=False
        )
        
        return JSONResponse(
            content=health_status,
            headers={"X-Health-Check": "true"}
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        # Record failed health check
        await record_request_metrics(
            endpoint="/monitoring/health",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Health check failed")

@router.get(
    "/performance",
    summary="Performance Metrics",
    description="Get comprehensive performance metrics including response times, cache efficiency, and endpoint performance.",
    response_description="Detailed performance metrics and statistics.",
)
async def get_performance_metrics():
    """
    Get comprehensive performance metrics for the API.
    
    **Metrics Included:**
    - **System Overview**: Uptime, total requests, success rates
    - **Response Times**: Average, P95, P99 response times
    - **Cache Performance**: Hit rates, sizes, evictions
    - **Endpoint Performance**: Breakdown by individual endpoints
    - **Recent Performance**: Last 100 requests analysis
    
    **Use Cases:**
    - Performance monitoring dashboards
    - Capacity planning
    - Optimization analysis
    - SLA monitoring
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        performance_data = monitor.get_performance_summary()
        response_time = time.time() - start_time
        
        # Record this performance metrics request
        await record_request_metrics(
            endpoint="/monitoring/performance",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content=performance_data,
            headers={"X-Performance-Metrics": "true"}
        )
        
    except Exception as e:
        logger.error(f"Performance metrics failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/performance",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve performance metrics")

@router.get(
    "/caches",
    summary="Cache Performance",
    description="Get detailed cache performance metrics including hit rates, sizes, and evictions.",
    response_description="Cache performance metrics for all caches.",
)
async def get_cache_metrics():
    """
    Get detailed cache performance metrics.
    
    **Cache Metrics:**
    - **Hit Rates**: Percentage of cache hits vs misses
    - **Sizes**: Current number of cached items
    - **Memory Usage**: Estimated memory consumption
    - **Evictions**: Number of items evicted due to TTL
    
    **Available Caches:**
    - **candle_cache**: Technical indicators and candlestick data
    - **quote_cache**: Price quotes and market intelligence
    
    **Use Cases:**
    - Cache optimization
    - Memory usage monitoring
    - Performance tuning
    - Capacity planning
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        performance_data = monitor.get_performance_summary()
        response_time = time.time() - start_time
        
        # Extract just cache metrics
        cache_metrics = performance_data.get("caches", {})
        
        # Record this cache metrics request
        await record_request_metrics(
            endpoint="/monitoring/caches",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content={
                "caches": cache_metrics,
                "timestamp": performance_data.get("timestamp"),
                "summary": {
                    "total_caches": len(cache_metrics),
                    "overall_hit_rate": sum(
                        cache.get("hit_rate", 0) for cache in cache_metrics.values()
                    ) / len(cache_metrics) if cache_metrics else 0,
                    "total_memory_mb": sum(
                        cache.get("memory_usage_mb", 0) for cache in cache_metrics.values()
                    )
                }
            },
            headers={"X-Cache-Metrics": "true"}
        )
        
    except Exception as e:
        logger.error(f"Cache metrics failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/caches",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve cache metrics")

@router.get(
    "/endpoints",
    summary="Endpoint Performance",
    description="Get performance breakdown by individual API endpoints.",
    response_description="Endpoint-specific performance metrics and statistics.",
)
async def get_endpoint_metrics():
    """
    Get performance breakdown by API endpoints.
    
    **Endpoint Metrics:**
    - **Request Counts**: Total requests per endpoint
    - **Response Times**: Average response times per endpoint
    - **Success Rates**: Success vs error counts
    - **Cache Performance**: Cache hit rates per endpoint
    
    **Use Cases:**
    - Endpoint optimization
    - Performance bottleneck identification
    - Resource allocation
    - API design improvements
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        performance_data = monitor.get_performance_summary()
        response_time = time.time() - start_time
        
        # Extract just endpoint performance
        endpoint_metrics = performance_data.get("endpoint_performance", {})
        
        # Record this endpoint metrics request
        await record_request_metrics(
            endpoint="/monitoring/endpoints",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content={
                "endpoints": endpoint_metrics,
                "timestamp": performance_data.get("timestamp"),
                "summary": {
                    "total_endpoints": len(endpoint_metrics),
                    "most_used_endpoint": max(
                        endpoint_metrics.items(),
                        key=lambda x: x[1].get("count", 0)
                    )[0] if endpoint_metrics else None,
                    "fastest_endpoint": min(
                        endpoint_metrics.items(),
                        key=lambda x: x[1].get("avg_time", float('inf'))
                    )[0] if endpoint_metrics else None,
                }
            },
            headers={"X-Endpoint-Metrics": "true"}
        )
        
    except Exception as e:
        logger.error(f"Endpoint metrics failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/endpoints",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve endpoint metrics")

@router.get(
    "/status",
    summary="System Status",
    description="Get quick system status overview with key metrics.",
    response_description="System status overview and key performance indicators.",
)
async def get_system_status():
    """
    Get quick system status overview.
    
    **Status Information:**
    - **Overall Health**: Healthy, Degraded, or Unhealthy
    - **Key Metrics**: Uptime, request rate, success rate
    - **Cache Status**: Overall cache performance
    - **Response Time**: Current average response time
    
    **Use Cases:**
    - Quick status checks
    - Status page integration
    - Monitoring system heartbeats
    - User confidence verification
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        
        # Get both health and performance data
        health_status = await monitor.get_health_status()
        performance_data = monitor.get_performance_summary()
        response_time = time.time() - start_time
        
        # Create status overview
        status_overview = {
            "status": health_status["status"],
            "overall_health": health_status["overall_health"],
            "uptime": performance_data["system"]["uptime_formatted"],
            "requests_per_minute": performance_data["system"]["requests_per_minute"],
            "success_rate": performance_data["system"]["success_rate"],
            "average_response_time": performance_data["system"]["average_response_time"],
            "cache_performance": {
                name: {
                    "hit_rate": metrics["hit_rate"],
                    "size": metrics["size"]
                }
                for name, metrics in performance_data["caches"].items()
            },
            "timestamp": performance_data["timestamp"]
        }
        
        # Record this status request
        await record_request_metrics(
            endpoint="/monitoring/status",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content=status_overview,
            headers={"X-System-Status": "true"}
        )
        
    except Exception as e:
        logger.error(f"System status failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/status",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")

@router.get(
    "/dashboard",
    summary="Performance Dashboard",
    description="Get HTML dashboard for real-time performance monitoring.",
    response_description="HTML dashboard page.",
    tags=["Monitoring"],
)
async def get_performance_dashboard():
    """
    Get HTML performance dashboard.
    
    **Features:**
    - Real-time system status
    - Performance metrics visualization
    - Cache performance monitoring
    - Endpoint performance breakdown
    - Auto-refresh every 30 seconds
    
    **Use Cases:**
    - DevOps monitoring
    - Performance analysis
    - System health checks
    - Capacity planning
    """
    try:
        # Read the dashboard HTML file
        import os
        dashboard_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "static", "dashboard.html")
        
        with open(dashboard_path, 'r') as f:
            html_content = f.read()
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content, status_code=200)
        
    except Exception as e:
        logger.error(f"Failed to serve dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to serve dashboard")
