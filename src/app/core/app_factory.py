import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.app.core.config import get_settings
from src.app.core.routers import include_all_routers
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
        title="Market Data API Platform",
        version="1.0.0",
        description="""
        # 🚀 Market Data API Platform
        
        **Multi-API platform** with organized endpoints by functional area.
        
        ## 📚 Available API Groups
        
        - **Market Data API** - Financial data, quotes, and market intelligence
        - **Utils API** - System performance, monitoring, and health checks
        
        ## 🔗 Endpoint Organization
        
        All endpoints are organized by tags below:
        - **Quotes, Candles, Articles, Streaming** - Market data operations
        - **Performance, Monitoring, Health** - System utilities and monitoring
        
        ---
        
        **Browse endpoints by their functional tags below!**
        """,
        openapi_url="/openapi.json",
        docs_url="/market-data-api/docs",
        redoc_url="/market-data-api/redoc",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 2,
            "displayRequestDuration": True,
            "syntaxHighlight": {"theme": "obsidian"},
            "tryItOutEnabled": True,
            "requestSnippetsEnabled": True,
            "defaultModelExpandDepth": 2,
            "defaultModelRendering": "example",
            "displayOperationId": True,
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
            "docExpansion": "list",
            "deepLinking": True,
            "persistAuthorization": True,
            "layout": "BaseLayout",
        },
        lifespan=lifespan,
    )

    settings = get_settings()
    
    # Add performance monitoring middleware
    app.add_middleware(PerformanceMonitoringMiddleware)
    app.add_middleware(CacheMonitoringMiddleware)
    
    # Include all routers in the main app with proper tag organization
    include_all_routers(app)
    
    print(f"🔧 App created with {len(app.routes)} routes")
    for route in app.routes:
        if hasattr(route, 'tags') and route.tags:
            print(f"   - {route.path} -> tags: {route.tags}")
    
    # Create a custom OpenAPI schema with organized tags and Market Data API as default
    def custom_openapi_with_groups():
        if app.openapi_schema:
            return app.openapi_schema
        
        # Get the base OpenAPI schema
        from fastapi.openapi.utils import get_openapi
        from src.app.swagger_config.contact import get_contact_info
        from src.app.swagger_config.servers import get_servers
        
        print("🔧 Generating custom OpenAPI schema with organized tags...")
        
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        
        # Add all tags from both API groups, with Market Data tags first (default)
        from src.app.swagger_config.tags import utils_tags_metadata, market_data_tags_metadata
        # Market Data tags first (default), then Utils tags
        all_tags = market_data_tags_metadata + utils_tags_metadata
        schema["tags"] = all_tags
        
        print(f"📋 Added {len(all_tags)} tags to OpenAPI schema:")
        for tag in all_tags:
            print(f"   - {tag['name']}: {tag['description'][:50]}...")
        
        schema["info"].update(get_contact_info())
        schema["servers"] = get_servers()
        
        app.openapi_schema = schema
        print("✅ OpenAPI schema generated successfully!")
        return schema
    
    app.openapi = custom_openapi_with_groups
    
    # Add a root endpoint to help users navigate
    @app.get("/")
    async def root():
        return {
            "message": "Market Data API Platform",
            "description": "Multi-API platform with organized endpoints by functional area",
            "available_apis": {
                "market_data": {
                    "name": "Market Data API", 
                    "description": "Financial data, quotes, and market intelligence",
                    "tags": ["Quotes", "Candles", "Articles", "Streaming"]
                },
                "utils": {
                    "name": "Utils API",
                    "description": "System performance, monitoring, and health checks",
                    "tags": ["Performance", "Monitoring", "Health"]
                }
            },
            "swagger_ui": "/market-data-api/docs",
            "redoc": "/market-data-api/redoc",
            "note": "Market Data API endpoints are shown first by default"
        }
    
    # Add a debug endpoint to check OpenAPI schema
    @app.get("/debug/openapi")
    async def debug_openapi():
        try:
            schema = app.openapi()
            return {
                "message": "OpenAPI schema generated successfully",
                "tags_count": len(schema.get("tags", [])),
                "paths_count": len(schema.get("paths", {})),
                "tags": [tag["name"] for tag in schema.get("tags", [])],
                "available_paths": list(schema.get("paths", {}).keys())
            }
        except Exception as e:
            return {
                "error": "Failed to generate OpenAPI schema",
                "detail": str(e)
            }
    
    return app
