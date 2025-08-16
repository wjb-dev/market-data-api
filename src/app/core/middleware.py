"""
Middleware for automatic request tracking and performance monitoring.
Automatically captures metrics for all API requests without manual instrumentation.
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.app.core.monitoring import record_request_metrics

logger = logging.getLogger(__name__)

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for automatic performance monitoring of all requests"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("Performance monitoring middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and capture performance metrics"""
        start_time = time.time()
        
        # Extract request information
        endpoint = request.url.path
        method = request.method
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Determine if it was a cache hit
            cache_hit = False
            if hasattr(response, 'headers'):
                cache_hit = response.headers.get("X-Cache") == "HIT"
            
            # Record successful request metrics
            await record_request_metrics(
                endpoint=endpoint,
                method=method,
                status_code=response.status_code,
                response_time=response_time,
                cache_hit=cache_hit,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            # Add performance headers
            if hasattr(response, 'headers'):
                response.headers["X-Response-Time"] = f"{response_time:.3f}s"
                response.headers["X-Request-ID"] = f"{int(start_time * 1000000)}"
            
            return response
            
        except Exception as e:
            # Calculate response time for failed requests
            response_time = time.time() - start_time
            
            # Record failed request metrics
            await record_request_metrics(
                endpoint=endpoint,
                method=method,
                status_code=500,
                response_time=response_time,
                cache_hit=False,
                error=str(e),
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            # Re-raise the exception
            raise

class CacheMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for monitoring cache performance and updating cache metrics"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("Cache monitoring middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and update cache metrics"""
        response = await call_next(request)
        
        # Update cache metrics if response has cache headers
        if hasattr(response, 'headers'):
            cache_header = response.headers.get("X-Cache")
            if cache_header:
                # Extract cache name from endpoint
                endpoint = request.url.path
                cache_name = self._get_cache_name_from_endpoint(endpoint)
                
                if cache_name:
                    # Update cache size and memory usage (simplified)
                    # In production, this would get actual cache statistics
                    from src.app.core.monitoring import get_performance_monitor
                    monitor = get_performance_monitor()
                    
                    # Placeholder values - would get actual cache stats
                    cache_size = 100  # Placeholder
                    memory_usage = 50.0  # Placeholder MB
                    
                    await monitor.update_cache_stats(cache_name, cache_size, memory_usage)
        
        return response
    
    def _get_cache_name_from_endpoint(self, endpoint: str) -> str:
        """Map endpoint to cache name"""
        if "candles" in endpoint:
            return "candle_cache"
        elif "quotes" in endpoint:
            return "quote_cache"
        else:
            return "unknown_cache"
