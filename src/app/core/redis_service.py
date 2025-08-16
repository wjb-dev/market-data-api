import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
import redis.asyncio as redis
from src.app.core.config import get_settings

logger = logging.getLogger(__name__)

class RedisService:
    """High-performance Redis caching service with connection pooling and optimization."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or "redis://localhost:6379"
        self._redis_client: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
        self._lock = asyncio.Lock()
        
    async def _get_client(self) -> redis.Redis:
        """Get Redis client with connection pooling."""
        if self._redis_client is None:
            async with self._lock:
                if self._redis_client is None:
                    try:
                        self._connection_pool = redis.ConnectionPool.from_url(
                            self.redis_url,
                            max_connections=20,
                            retry_on_timeout=True,
                            socket_keepalive=True,
                            socket_keepalive_options={},
                            health_check_interval=30
                        )
                        self._redis_client = redis.Redis(
                            connection_pool=self._connection_pool,
                            decode_responses=True,
                            socket_timeout=1.0,
                            socket_connect_timeout=1.0
                        )
                        # Test connection
                        await self._redis_client.ping()
                        logger.info("✅ Redis connection established successfully")
                    except Exception as e:
                        logger.error(f"❌ Failed to connect to Redis: {e}")
                        raise
        return self._redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis with error handling."""
        try:
            client = await self._get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set value in Redis with TTL."""
        try:
            client = await self._get_client()
            serialized = json.dumps(value, default=str)
            await client.setex(key, ttl_seconds, serialized)
            return True
        except Exception as e:
            logger.warning(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            client = await self._get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        try:
            client = await self._get_client()
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis delete pattern error for {pattern}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            client = await self._get_client()
            return bool(await client.exists(key))
        except Exception as e:
            logger.warning(f"Redis exists error for key {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get TTL for key in seconds."""
        try:
            client = await self._get_client()
            return await client.ttl(key)
        except Exception as e:
            logger.warning(f"Redis TTL error for key {key}: {e}")
            return -1
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        try:
            client = await self._get_client()
            return await client.incrby(key, amount)
        except Exception as e:
            logger.warning(f"Redis increment error for key {key}: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get Redis performance statistics."""
        try:
            client = await self._get_client()
            info = await client.info()
            return {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.warning(f"Redis stats error: {e}")
            return {}
    
    async def close(self):
        """Close Redis connections."""
        if self._redis_client:
            await self._redis_client.close()
        if self._connection_pool:
            await self._connection_pool.disconnect()

# Global Redis service instance
_redis_service: Optional[RedisService] = None

async def get_redis_service() -> RedisService:
    """Get global Redis service instance."""
    global _redis_service
    if _redis_service is None:
        settings = get_settings()
        redis_url = getattr(settings, 'redis_url', None)
        _redis_service = RedisService(redis_url)
    return _redis_service

async def close_redis_service():
    """Close global Redis service."""
    global _redis_service
    if _redis_service:
        await _redis_service.close()
        _redis_service = None
