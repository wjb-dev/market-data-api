import os
from redis import Redis

_client: Redis | None = None

def get_redis_client() -> Redis:
    global _client
    if _client is None:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        _client = Redis(host=redis_host, port=redis_port, decode_responses=True)
    return _client
