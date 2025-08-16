import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.app.core.config import get_settings
from src.app.core.routers import include_routers
from src.app.core.runtime import runtime
from src.app.swagger_config.configurator import custom_openapi
from src.app.core.middleware import PerformanceMonitoringMiddleware, CacheMonitoringMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):

    settings = get_settings()

    await runtime.start(settings, app)
    yield
    await runtime.destroy()

def create_app() -> FastAPI:
    app = FastAPI(
            title=get_settings().app_name,
    version=get_settings().version,
    description=get_settings().description,
        openapi_url="/openapi.json",
        docs_url="/market-data-api/docs",
        redoc_url=None,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,
            "displayRequestDuration": True,
            "syntaxHighlight": {"theme": "obsidian"},
        },
        lifespan=lifespan,
    )

    settings = get_settings()
    app.openapi = lambda: custom_openapi(app=app, settings=settings)
    
    # Add performance monitoring middleware
    app.add_middleware(PerformanceMonitoringMiddleware)
    app.add_middleware(CacheMonitoringMiddleware)
    
    include_routers(app)
    return app
