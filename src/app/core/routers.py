from src.app.api.v1.routers.health import router as health_router
from src.app.api.v1.routers.prices import router as prices_router
from src.app.api.v1.routers.streaming import router as streaming_router


def include_routers(app):
    app.include_router(health_router)
    app.include_router(prices_router)
    app.include_router(streaming_router)

