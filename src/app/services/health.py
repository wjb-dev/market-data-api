from src.app.core.config import get_settings

from src.app.services.redis.redis_service import check_redis



def get_health() -> dict:
    services = {}
    services["redis"] = check_redis()
    
    settings = get_settings()
    return {
        "service": settings.app_name,
        "status": "ok",
        "version": settings.version,
        "services": services,
    }
