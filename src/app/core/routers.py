from src.app.api.v1.routers.health import router as health_router


def include_routers(app):
    app.include_router(health_router)
    
