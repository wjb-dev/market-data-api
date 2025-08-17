"""
Performance and monitoring schemas for the Market Data API
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class HTTPClientMetrics(BaseModel):
    """HTTP client performance metrics"""
    total_requests: int = Field(..., description="Total number of requests")
    success_rate: float = Field(..., description="Success rate percentage")
    avg_response_time: float = Field(..., description="Average response time in seconds")
    p95_response_time: float = Field(..., description="95th percentile response time")
    p99_response_time: float = Field(..., description="99th percentile response time")
    error_rate: float = Field(..., description="Error rate percentage")
    requests_per_second: float = Field(..., description="Requests per second")


class CacheMetrics(BaseModel):
    """Cache performance metrics for all cache types"""
    candles: Dict[str, Any] = Field(..., description="Candles cache metrics")
    quotes: Dict[str, Any] = Field(..., description="Quotes cache metrics")
    news: Dict[str, Any] = Field(..., description="News cache metrics")


class RedisMetrics(BaseModel):
    """Redis performance metrics"""
    connected: bool = Field(..., description="Redis connection status")
    memory_usage: str = Field(..., description="Memory usage")
    operations_per_second: int = Field(..., description="Operations per second")
    connected_clients: int = Field(..., description="Number of connected clients")
    uptime_seconds: int = Field(..., description="Uptime in seconds")


class SystemMetrics(BaseModel):
    """System performance metrics"""
    uptime_seconds: int = Field(..., description="System uptime in seconds")
    total_requests: int = Field(..., description="Total requests processed")
    active_connections: int = Field(..., description="Active connections")
    memory_usage: str = Field(..., description="System memory usage")
    cpu_usage_percent: float = Field(..., description="CPU usage percentage")


class PerformanceOverview(BaseModel):
    """Complete performance overview"""
    service: str = Field(..., description="Service name")
    timestamp: datetime = Field(..., description="Metrics timestamp")
    http_client: HTTPClientMetrics = Field(..., description="HTTP client metrics")
    caches: Dict[str, CacheMetrics] = Field(..., description="Cache metrics by type")
    redis: RedisMetrics = Field(..., description="Redis metrics")
    system: SystemMetrics = Field(..., description="System metrics")


class HealthCheck(BaseModel):
    """Individual health check result"""
    status: str = Field(..., description="Health status")
    response_time: float = Field(..., description="Response time in seconds")
    threshold: Optional[float] = Field(None, description="Threshold value")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class SystemHealth(BaseModel):
    """Complete system health status"""
    status: str = Field(..., description="Overall system health")
    timestamp: datetime = Field(..., description="Health check timestamp")
    checks: Dict[str, HealthCheck] = Field(..., description="Individual health checks")
    overall_health: str = Field(..., description="Overall health status")
    performance_score: float = Field(..., description="Performance score (0-100)")
    uptime_seconds: int = Field(..., description="System uptime in seconds")
    issues: Optional[List[str]] = Field(None, description="List of issues if unhealthy")
