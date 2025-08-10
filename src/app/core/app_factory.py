import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.app.core.config import settings
from src.app.core.routers import include_routers
from src.app.core.runtime import runtime
from src.app.swagger_config.configurator import custom_openapi

@asynccontextmanager
async def lifespan(app: FastAPI):
    

    await runtime.start(settings, app)
    yield
    await runtime.destroy()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=settings.description,
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

    app.openapi = lambda: custom_openapi(app=app, settings=settings)
    include_routers(app)
    return app
