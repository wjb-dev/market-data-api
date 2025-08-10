from src.app.core.config import settings

from src.app.services.redis.redis_service import check_redis



def get_health() -> dict:
    services = {}
    services["redis"] = check_redis()
    
    return {
        "service": settings.app_name,
        "status": "ok",
        "version": settings.version,
        "services": services,
    }
