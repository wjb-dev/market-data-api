from src.app.api.v1.routers.health import router as health_router
from src.app.api.v1.routers.candles import router as candles_router
from src.app.api.v1.routers.quotes import router as quotes_router
from src.app.api.v1.routers.streaming import router as streaming_router
from src.app.api.v1.routers.monitoring import router as monitoring_router
from src.app.api.v1.routers.articles import router as articles_router
from src.app.api.v1.routers.performance import router as performance_router

# Define which routers belong to which API groups
UTILS_ROUTERS = [
    health_router,
    monitoring_router,
    performance_router
]

MARKET_DATA_ROUTERS = [
    candles_router,
    quotes_router,
    streaming_router,
    articles_router
]

def include_routers(app, include_utils=True, include_market_data=True):
    """
    Include routers in the app based on the specified API groups.
    
    Args:
        app: FastAPI app instance
        include_utils: Whether to include utils-related routers (health, monitoring, performance)
        include_market_data: Whether to include market data routers (candles, quotes, streaming, articles)
    """
    if include_utils:
        for router in UTILS_ROUTERS:
            app.include_router(router)
    
    if include_market_data:
        for router in MARKET_DATA_ROUTERS:
            app.include_router(router)

def include_all_routers(app):
    """Include all routers in a single app (backward compatibility)."""
    for router in UTILS_ROUTERS + MARKET_DATA_ROUTERS:
        app.include_router(router)


