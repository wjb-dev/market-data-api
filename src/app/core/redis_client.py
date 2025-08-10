from redis import Redis
from src.app.core.config import settings

def get_redis_client() -> Redis:
    return Redis(host=settings.redis_host, port=settings.redis_port, db=0)
