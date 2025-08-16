"""
Performance monitoring and metrics collection for the Market Data API.
Provides real-time insights into API performance, cache efficiency, and system health.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)

@dataclass
class RequestMetrics:
    """Individual request performance metrics"""
    endpoint: str
    method: str
    status_code: int
    response_time: float
    timestamp: datetime
    cache_hit: bool = False
    error: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    cache_name: str
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0
    memory_usage: float = 0.0
    hit_rate: float = 0.0
    
    def update_hit_rate(self):
        """Calculate current hit rate"""
        total = self.hits + self.misses
        self.hit_rate = (self.hits / total * 100) if total > 0 else 0.0

@dataclass
class SystemMetrics:
    """System-wide performance metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    requests_per_minute: float = 0.0
    active_connections: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

class PerformanceMonitor:
    """Central performance monitoring system"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.request_history: deque = deque(maxlen=max_history)
        self.cache_metrics: Dict[str, CacheMetrics] = defaultdict(lambda: CacheMetrics(cache_name=""))
        self.system_metrics = SystemMetrics()
        self.start_time = datetime.now()
        self._lock = asyncio.Lock()
        
        # Initialize cache metrics
        self.cache_metrics["candle_cache"] = CacheMetrics(cache_name="candle_cache")
        self.cache_metrics["quote_cache"] = CacheMetrics(cache_name="quote_cache")
        
        logger.info("Performance monitor initialized")
    
    async def record_request(self, metrics: RequestMetrics):
        """Record a single request's performance metrics"""
        async with self._lock:
            self.request_history.append(metrics)
            
            # Update system metrics
            self.system_metrics.total_requests += 1
            if metrics.status_code < 400:
                self.system_metrics.successful_requests += 1
            else:
                self.system_metrics.failed_requests += 1
            
            # Update response time statistics
            self._update_response_time_stats(metrics.response_time)
            
            # Update cache metrics if applicable
            if hasattr(metrics, 'cache_hit') and metrics.cache_hit:
                self._update_cache_metrics(metrics.endpoint, True)
            else:
                self._update_cache_metrics(metrics.endpoint, False)
    
    def _update_response_time_stats(self, response_time: float):
        """Update response time statistics"""
        # Simple moving average for now
        current_avg = self.system_metrics.average_response_time
        total_requests = self.system_metrics.total_requests
        
        if total_requests == 1:
            self.system_metrics.average_response_time = response_time
        else:
            self.system_metrics.average_response_time = (
                (current_avg * (total_requests - 1) + response_time) / total_requests
            )
        
        # Calculate percentiles (simplified)
        response_times = [m.response_time for m in self.request_history]
        if len(response_times) >= 10:  # Need enough data for percentiles
            sorted_times = sorted(response_times)
            self.system_metrics.p95_response_time = sorted_times[int(len(sorted_times) * 0.95)]
            self.system_metrics.p99_response_time = sorted_times[int(len(sorted_times) * 0.99)]
    
    def _update_cache_metrics(self, endpoint: str, cache_hit: bool):
        """Update cache performance metrics"""
        cache_name = self._get_cache_name_from_endpoint(endpoint)
        if cache_name in self.cache_metrics:
            if cache_hit:
                self.cache_metrics[cache_name].hits += 1
            else:
                self.cache_metrics[cache_name].misses += 1
            self.cache_metrics[cache_name].update_hit_rate()
    
    def _get_cache_name_from_endpoint(self, endpoint: str) -> str:
        """Map endpoint to cache name"""
        if "candles" in endpoint:
            return "candle_cache"
        elif "quotes" in endpoint:
            return "quote_cache"
        else:
            return "unknown_cache"
    
    async def update_cache_stats(self, cache_name: str, size: int, memory_usage: float = 0.0):
        """Update cache statistics"""
        if cache_name in self.cache_metrics:
            self.cache_metrics[cache_name].size = size
            self.cache_metrics[cache_name].memory_usage = memory_usage
    
    async def record_cache_eviction(self, cache_name: str):
        """Record a cache eviction event"""
        if cache_name in self.cache_metrics:
            self.cache_metrics[cache_name].evictions += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        now = datetime.now()
        uptime = now - self.start_time
        
        # Calculate requests per minute
        if uptime.total_seconds() > 0:
            self.system_metrics.requests_per_minute = (
                self.system_metrics.total_requests / (uptime.total_seconds() / 60)
            )
        
        # Get recent performance (last 100 requests)
        recent_requests = list(self.request_history)[-100:]
        recent_response_times = [r.response_time for r in recent_requests if r.status_code < 400]
        
        recent_metrics = {
            "recent_avg_response_time": statistics.mean(recent_response_times) if recent_response_times else 0.0,
            "recent_p95_response_time": statistics.quantiles(recent_response_times, n=20)[18] if len(recent_response_times) >= 20 else 0.0,
            "recent_requests_per_minute": len(recent_requests) / 1.0,  # Assuming 1 minute window
        }
        
        return {
            "system": {
                "uptime_seconds": uptime.total_seconds(),
                "uptime_formatted": str(uptime).split('.')[0],  # Remove microseconds
                "total_requests": self.system_metrics.total_requests,
                "successful_requests": self.system_metrics.successful_requests,
                "failed_requests": self.system_metrics.failed_requests,
                "success_rate": (self.system_metrics.successful_requests / self.system_metrics.total_requests * 100) if self.system_metrics.total_requests > 0 else 0.0,
                "average_response_time": round(self.system_metrics.average_response_time, 3),
                "p95_response_time": round(self.system_metrics.p95_response_time, 3),
                "p99_response_time": round(self.system_metrics.p99_response_time, 3),
                "requests_per_minute": round(self.system_metrics.requests_per_minute, 2),
            },
            "caches": {
                name: {
                    "hits": metrics.hits,
                    "misses": metrics.misses,
                    "hit_rate": round(metrics.hit_rate, 2),
                    "size": metrics.size,
                    "memory_usage_mb": round(metrics.memory_usage, 2),
                    "evictions": metrics.evictions,
                }
                for name, metrics in self.cache_metrics.items()
            },
            "recent_performance": recent_metrics,
            "endpoint_performance": self._get_endpoint_performance(),
            "timestamp": now.isoformat()
        }
    
    def _get_endpoint_performance(self) -> Dict[str, Any]:
        """Get performance breakdown by endpoint"""
        endpoint_stats = defaultdict(lambda: {
            "count": 0,
            "total_time": 0.0,
            "avg_time": 0.0,
            "success_count": 0,
            "error_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        })
        
        for request in self.request_history:
            endpoint = request.endpoint
            stats = endpoint_stats[endpoint]
            
            stats["count"] += 1
            stats["total_time"] += request.response_time
            
            if request.status_code < 400:
                stats["success_count"] += 1
            else:
                stats["error_count"] += 1
            
            if hasattr(request, 'cache_hit'):
                if request.cache_hit:
                    stats["cache_hits"] += 1
                else:
                    stats["cache_misses"] += 1
        
        # Calculate averages
        for stats in endpoint_stats.values():
            if stats["count"] > 0:
                stats["avg_time"] = round(stats["total_time"] / stats["count"], 3)
                stats["total_time"] = round(stats["total_time"], 3)
        
        return dict(endpoint_stats)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        now = datetime.now()
        uptime = now - self.start_time
        
        # Health checks
        health_checks = {
            "api_responsive": True,  # If we can call this, API is responsive
            "cache_healthy": all(
                metrics.hit_rate > 50.0 for metrics in self.cache_metrics.values()
            ),
            "response_time_healthy": self.system_metrics.average_response_time < 1.0,  # Under 1 second
            "error_rate_healthy": (
                self.system_metrics.failed_requests / self.system_metrics.total_requests < 0.05
            ) if self.system_metrics.total_requests > 0 else True,
        }
        
        overall_health = all(health_checks.values())
        
        return {
            "status": "healthy" if overall_health else "degraded",
            "overall_health": overall_health,
            "health_checks": health_checks,
            "uptime_seconds": uptime.total_seconds(),
            "timestamp": now.isoformat()
        }

# Global monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

async def record_request_metrics(
    endpoint: str,
    method: str,
    status_code: int,
    response_time: float,
    cache_hit: bool = False,
    error: Optional[str] = None,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
):
    """Convenience function to record request metrics"""
    monitor = get_performance_monitor()
    metrics = RequestMetrics(
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        response_time=response_time,
        timestamp=datetime.now(),
        cache_hit=cache_hit,
        error=error,
        user_agent=user_agent,
        ip_address=ip_address
    )
    await monitor.record_request(metrics)
