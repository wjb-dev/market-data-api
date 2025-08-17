import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from src.app.core.redis_service import get_redis_service
import json

logger = logging.getLogger(__name__)

class HybridCache:
    """Hybrid cache with Redis primary and in-memory fallback."""
    
    def __init__(self, ttl_seconds: int = 300, cache_name: str = "default"):
        self.ttl = timedelta(seconds=ttl_seconds)
        self.cache_name = cache_name
        self._memory_cache: Dict[str, Tuple[Any, datetime]] = {}
        self._lock = asyncio.Lock()
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._redis_hits = 0
        self._memory_hits = 0
        self._redis_errors = 0
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with Redis priority."""
        self._total_requests += 1
        
        try:
            # Try Redis first
            redis_service = await get_redis_service()
            redis_value = await redis_service.get(key)
            
            if redis_value is not None:
                self._cache_hits += 1
                self._redis_hits += 1
                logger.debug(f"Redis HIT for {self.cache_name}: {key}")
                return redis_value
                
        except Exception as e:
            self._redis_errors += 1
            # Fall back to memory cache if Redis fails
            logger.debug(f"Redis failed for {self.cache_name}: {key} - falling back to memory: {e}")
        
        # Fall back to memory cache
        async with self._lock:
            if key in self._memory_cache:
                value, timestamp = self._memory_cache[key]
                if datetime.now() - timestamp < self.ttl:
                    self._cache_hits += 1
                    self._memory_hits += 1
                    logger.debug(f"Memory HIT for {self.cache_name}: {key}")
                    return value
                else:
                    # Expired, remove it
                    del self._memory_cache[key]
        
        self._cache_misses += 1
        logger.debug(f"Cache MISS for {self.cache_name}: {key}")
        return None
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set value in both Redis and memory cache."""
        ttl = ttl_seconds or self.ttl.total_seconds()
        timestamp = datetime.now()
        
        # Set in memory cache
        async with self._lock:
            self._memory_cache[key] = (value, timestamp)
        
        # Try to set in Redis
        try:
            redis_service = await get_redis_service()
            await redis_service.set(key, value, int(ttl))
            logger.debug(f"Set in Redis for {self.cache_name}: {key}")
        except Exception as e:
            logger.debug(f"Redis set failed for {self.cache_name}: {key} - {e}")
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete from both caches."""
        # Delete from memory
        async with self._lock:
            if key in self._memory_cache:
                del self._memory_cache[key]
        
        # Try to delete from Redis
        try:
            redis_service = await get_redis_service()
            await redis_service.delete(key)
        except Exception as e:
            logger.debug(f"Redis delete failed for {self.cache_name}: {key} - {e}")
        
        return True
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern from both caches."""
        deleted_count = 0
        
        # Delete from memory cache
        async with self._lock:
            keys_to_delete = [k for k in self._memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._memory_cache[key]
                deleted_count += 1
        
        # Try to delete from Redis
        try:
            redis_service = await get_redis_service()
            redis_deleted = await redis_service.delete_pattern(pattern)
            deleted_count += redis_deleted
        except Exception as e:
            logger.debug(f"Redis delete pattern failed: {e}")
        
        return deleted_count
    
    async def clear(self) -> int:
        """Clear all caches."""
        count = 0
        
        # Clear memory cache
        async with self._lock:
            count = len(self._memory_cache)
            self._memory_cache.clear()
        
        # Try to clear Redis (this is expensive, so we'll do it selectively)
        try:
            redis_service = await get_redis_service()
            # Clear only keys with our cache name prefix
            pattern = f"{self.cache_name}:*"
            redis_deleted = await redis_service.delete_pattern(pattern)
            count += redis_deleted
        except Exception as e:
            logger.debug(f"Redis clear failed for {self.cache_name}: {e}")
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._total_requests or 1
        cache_hit_rate = (self._cache_hits / total_requests) * 100 if total_requests > 0 else 0
        
        return {
            "cache_name": self.cache_name,
            "total_requests": self._total_requests,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "redis_hits": self._redis_hits,
            "memory_hits": self._memory_hits,
            "redis_errors": self._redis_errors,
            "memory_cache_size": len(self._memory_cache),
            "ttl_seconds": self.ttl.total_seconds()
        }

# Specialized cache instances
class CandlesCache(HybridCache):
    """Optimized cache for candle data with longer TTL."""
    def __init__(self):
        super().__init__(ttl_seconds=300, cache_name="candles")  # 5 minutes

class QuotesCache(HybridCache):
    """Optimized cache for quote data with shorter TTL."""
    def __init__(self):
        super().__init__(ttl_seconds=30, cache_name="quotes")  # 30 seconds

class NewsCache(HybridCache):
    """Optimized cache for news data with medium TTL."""
    def __init__(self):
        super().__init__(ttl_seconds=180, cache_name="news")  # 3 minutes

# Global cache instances
_candles_cache: Optional[CandlesCache] = None
_quotes_cache: Optional[QuotesCache] = None
_news_cache: Optional[NewsCache] = None

def get_candles_cache() -> CandlesCache:
    """Get global candles cache instance."""
    global _candles_cache
    if _candles_cache is None:
        _candles_cache = CandlesCache()
    return _candles_cache

def get_quotes_cache() -> QuotesCache:
    """Get global quotes cache instance."""
    global _quotes_cache
    if _quotes_cache is None:
        _quotes_cache = QuotesCache()
    return _quotes_cache

def get_news_cache() -> NewsCache:
    """Get global news cache instance."""
    global _news_cache
    if _news_cache is None:
        _news_cache = NewsCache()
    return _news_cache
