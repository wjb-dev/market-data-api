import asyncio
import logging
import time
from typing import Any, Dict, Optional
import httpx
# No config dependency to avoid circular imports

logger = logging.getLogger(__name__)

class OptimizedHTTPClient:
    """High-performance HTTP client with connection pooling and optimization."""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_response_time = 0.0
        self._request_times: list[float] = []
        
    async def _get_client(self) -> httpx.AsyncClient:
        """Get HTTP client with connection pooling."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    # Use default values for now
                    limits = httpx.Limits(
                        max_keepalive_connections=20,
                        max_connections=100,
                        keepalive_expiry=30.0
                    )
                    timeout = httpx.Timeout(
                        connect=2.0,
                        read=10.0,
                        write=10.0,
                        pool=30.0
                    )
                    self._client = httpx.AsyncClient(
                        limits=limits,
                        timeout=timeout,
                        http2=False,  # Disable HTTP2 for compatibility
                        follow_redirects=True
                    )
                    logger.info("✅ Optimized HTTP client created with connection pooling")
        return self._client
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Optimized GET request with performance tracking."""
        start_time = time.time()
        try:
            client = await self._get_client()
            response = await client.get(url, **kwargs)
            self._record_request(start_time, success=True)
            return response
        except Exception as e:
            self._record_request(start_time, success=False)
            raise
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Optimized POST request with performance tracking."""
        start_time = time.time()
        try:
            client = await self._get_client()
            response = await client.post(url, **kwargs)
            self._record_request(start_time, success=True)
            return response
        except Exception as e:
            self._record_request(start_time, success=False)
            raise
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _record_request(self, start_time: float, success: bool = True):
        """Record request performance metrics."""
        response_time = time.time() - start_time
        self._total_requests += 1
        self._total_response_time += response_time
        self._request_times.append(response_time)
        
        if success:
            self._successful_requests += 1
        else:
            self._failed_requests += 1
        
        # Keep only last 1000 request times for memory efficiency
        if len(self._request_times) > 1000:
            self._request_times = self._request_times[-1000:]
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get HTTP client performance statistics."""
        if not self._request_times:
            return {
                "total_requests": 0,
                "success_rate_percent": 0.0,
                "avg_response_time_ms": 0.0,
                "p95_response_time_ms": 0.0,
                "p99_response_time_ms": 0.0
            }
        
        sorted_times = sorted(self._request_times)
        n = len(sorted_times)
        
        avg_response_time = self._total_response_time / n
        p95_index = int(0.95 * n)
        p99_index = int(0.99 * n)
        
        success_rate = (self._successful_requests / self._total_requests) * 100 if self._total_requests > 0 else 0
        
        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "success_rate_percent": round(success_rate, 2),
            "avg_response_time_ms": round(avg_response_time * 1000, 2),
            "p95_response_time_ms": round(sorted_times[p95_index] * 1000, 2),
            "p99_response_time_ms": round(sorted_times[p99_index] * 1000, 2),
            "min_response_time_ms": round(min(sorted_times) * 1000, 2),
            "max_response_time_ms": round(max(sorted_times) * 1000, 2)
        }

# Global HTTP client instance
_http_client: Optional[OptimizedHTTPClient] = None

def get_http_client() -> OptimizedHTTPClient:
    """Get global HTTP client instance."""
    global _http_client
    if _http_client is None:
        _http_client = OptimizedHTTPClient()
    return _http_client

async def close_http_client():
    """Close global HTTP client."""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None
