from redis import Redis
from src.app.core.config import get_settings

def get_redis_client() -> Redis:
    settings = get_settings()
    return Redis(host=settings.redis_host, port=settings.redis_port, db=0)
