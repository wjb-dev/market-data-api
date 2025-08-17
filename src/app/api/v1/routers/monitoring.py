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
from src.app.schemas.performance import SystemHealth, HealthCheck

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get(
    "/health",
    response_model=SystemHealth,
    summary="System Health Check",
    description="""
    Get comprehensive system health status with detailed health checks and performance metrics.
    
    **Health Checks:**
    - **API Responsive:** Basic API availability and response time
    - **Cache Healthy:** Cache hit rates above 50% threshold
    - **Response Time Healthy:** Average response time under 1 second
    - **Error Rate Healthy:** Error rate below 5% threshold
    - **Redis Connected:** Database connectivity and performance
    - **Memory Usage:** System memory utilization within limits
    
    **Health Status Levels:**
    - **🟢 Healthy:** All systems operating normally
    - **🟡 Warning:** Some metrics approaching thresholds
    - **🔴 Critical:** System issues requiring attention
    - **⚫ Unknown:** Unable to determine status
    
    **Use Cases:**
    - Load balancer health checks
    - Monitoring system integration
    - DevOps automation
    - User confidence verification
    - SLA compliance monitoring
    
    **Response Headers:**
    - `X-Health-Check: true` - Identifies health check requests
    - `X-Response-Time: 0.002` - Health check response time
    - `X-Cache-Status: healthy` - Cache health indicator
    
    **Performance:** Sub-10ms response time for health checks
    **Frequency:** Recommended every 30 seconds for production
    """,
    responses={
        200: {
            "description": "System is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "checks": {
                            "api_responsive": {
                                "status": "healthy",
                                "response_time": 0.002,
                                "threshold": 0.100
                            },
                            "cache_healthy": {
                                "status": "healthy",
                                "hit_rate": 78.4,
                                "threshold": 50.0
                            },
                            "response_time_healthy": {
                                "status": "healthy",
                                "avg_time": 0.125,
                                "threshold": 1.000
                            },
                            "error_rate_healthy": {
                                "status": "healthy",
                                "error_rate": 1.5,
                                "threshold": 5.0
                            },
                            "redis_connected": {
                                "status": "healthy",
                                "response_time": 0.005,
                                "memory_usage": "45.2MB"
                            }
                        },
                        "overall_health": "healthy",
                        "performance_score": 98.5,
                        "uptime_seconds": 86400
                    }
                }
            },
            "headers": {
                "X-Health-Check": {"description": "Health check identifier", "schema": {"type": "string"}},
                "X-Response-Time": {"description": "Health check response time", "schema": {"type": "string"}},
                "X-Cache-Status": {"description": "Cache health status", "schema": {"type": "string"}}
            }
        },
        503: {
            "description": "System is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "checks": {
                            "api_responsive": {"status": "healthy", "response_time": 0.002},
                            "cache_healthy": {"status": "critical", "hit_rate": 25.0, "threshold": 50.0},
                            "redis_connected": {"status": "critical", "error": "Connection timeout"}
                        },
                        "overall_health": "critical",
                        "performance_score": 45.2,
                        "issues": ["Cache performance below threshold", "Redis connection failed"]
                    }
                }
            }
        },
        500: {
            "description": "Health check failed",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Health check failed: Unable to connect to monitoring service"
                    }
                }
            }
        }
    },
    tags=["Monitoring"]
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
    response_model=Dict[str, Any],
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
    response_model=Dict[str, Any],
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
    response_model=Dict[str, Any],
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
    "/recent-requests",
    response_model=Dict[str, Any],
    summary="Recent Requests Analysis",
    description="Get a summary of the most recent requests processed by the API.",
    response_description="Summary of recent requests, including endpoint, method, status, and response time.",
)
async def get_recent_requests():
    """
    Get a summary of the most recent requests processed by the API.
    
    **Recent Requests:**
    - **Endpoint**: The API endpoint that received the request
    - **Method**: HTTP method (GET, POST, etc.)
    - **Status**: HTTP status code (200, 404, 500, etc.)
    - **Response Time**: Time taken to process the request
    - **Cache Hit**: Whether the request was served from cache
    
    **Use Cases:**
    - Debugging recent issues
    - Performance analysis
    - Monitoring API usage
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        recent_requests = monitor.get_recent_requests()
        response_time = time.time() - start_time
        
        # Record this recent requests request
        await record_request_metrics(
            endpoint="/monitoring/recent-requests",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content=recent_requests,
            headers={"X-Recent-Requests": "true"}
        )
        
    except Exception as e:
        logger.error(f"Recent requests failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/recent-requests",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve recent requests")

@router.get(
    "/status",
    response_model=Dict[str, Any],
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
    response_model=Dict[str, Any],
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

@router.get(
    "/errors",
    response_model=Dict[str, Any],
    summary="Error Tracking",
    description="Get a summary of recent errors encountered by the API.",
    response_description="Summary of recent errors, including endpoint, method, status, and error message.",
)
async def get_error_summary():
    """
    Get a summary of recent errors encountered by the API.
    
    **Error Summary:**
    - **Endpoint**: The API endpoint where the error occurred
    - **Method**: HTTP method (GET, POST, etc.)
    - **Status**: HTTP status code (500, 404, etc.)
    - **Error Message**: Description of the error
    - **Timestamp**: When the error occurred
    
    **Use Cases:**
    - Debugging application issues
    - Performance analysis
    - SLA compliance monitoring
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        error_summary = monitor.get_error_summary()
        response_time = time.time() - start_time
        
        # Record this error summary request
        await record_request_metrics(
            endpoint="/monitoring/errors",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content=error_summary,
            headers={"X-Error-Summary": "true"}
        )
        
    except Exception as e:
        logger.error(f"Error summary failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/errors",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve error summary")

@router.get(
    "/trends",
    response_model=Dict[str, Any],
    summary="Performance Trends",
    description="Get historical performance trends and patterns.",
    response_description="Performance trends data over a specified time period.",
)
async def get_performance_trends():
    """
    Get historical performance trends and patterns.
    
    **Trends Data:**
    - **Uptime**: System uptime over time
    - **Request Rate**: Number of requests per minute
    - **Success Rate**: Percentage of successful requests
    - **Average Response Time**: Average time taken for requests
    - **Cache Hit Rate**: Percentage of cache hits
    - **Memory Usage**: System memory utilization
    
    **Use Cases:**
    - Historical performance analysis
    - Capacity planning
    - System stability monitoring
    - SLA compliance tracking
    """
    try:
        start_time = time.time()
        monitor = get_performance_monitor()
        trends_data = monitor.get_performance_trends()
        response_time = time.time() - start_time
        
        # Record this trends request
        await record_request_metrics(
            endpoint="/monitoring/trends",
            method="GET",
            status_code=200,
            response_time=response_time,
            cache_hit=False
        )
        
        return JSONResponse(
            content=trends_data,
            headers={"X-Performance-Trends": "true"}
        )
        
    except Exception as e:
        logger.error(f"Performance trends failed: {str(e)}")
        # Record failed request
        await record_request_metrics(
            endpoint="/monitoring/trends",
            method="GET",
            status_code=500,
            response_time=0.0,
            cache_hit=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Failed to retrieve performance trends")
