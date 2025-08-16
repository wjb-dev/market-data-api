from src.app.api.v1.routers.health import router as health_router
from src.app.api.v1.routers.candles import router as candles_router
from src.app.api.v1.routers.quotes import router as quotes_router
from src.app.api.v1.routers.streaming import router as streaming_router
from src.app.api.v1.routers.monitoring import router as monitoring_router
from src.app.api.v1.routers.articles import router as articles_router
from src.app.api.v1.routers.performance import router as performance_router



def include_routers(app):
    app.include_router(health_router)
    app.include_router(candles_router)
    app.include_router(quotes_router)
    app.include_router(streaming_router)
    app.include_router(monitoring_router)
    app.include_router(articles_router)
    app.include_router(performance_router)


