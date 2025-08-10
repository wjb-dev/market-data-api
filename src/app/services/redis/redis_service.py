from haraka.PyFast.core.interfaces import Service
from redis import Redis

from src.app.core.redis_client import get_redis_client

def check_redis() -> str:
    try:
        return "Up" if get_redis_client().ping() else "Down"
    except Exception:
        return "Unavailable"

class RedisService(Service):
    def __init__(self):
        super().__init__()  # <- no `name="redis"` passed
        self.name = "redis"  # <- set it manually
        self.client: Redis | None = None

    async def startup(self):
        from src.app.core.redis_client import get_redis_client
        self.client = get_redis_client()
        try:
            self.client.ping()
            self.runtime.mark_ready(self.name)
        except Exception as e:
            self.runtime.logger.error("❌ Redis ping failed", extra={"error": str(e)})
            raise

    async def shutdown(self):
        self.client = None

