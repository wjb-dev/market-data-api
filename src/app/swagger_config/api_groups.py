from typing import Dict, List
from fastapi import FastAPI
from .tags import utils_tags_metadata, market_data_tags_metadata

# API Group Definitions
API_GROUPS = {
    "utils": {
        "title": "Utils API",
        "description": """
        # 🛠️ Utils API - System Performance & Monitoring
        
        **System utilities and performance monitoring** for the Market Data API platform.
        
        ## 🔧 Available Endpoints
        
        - **Performance Metrics:** Cache statistics, response times, and system performance
        - **System Monitoring:** Health checks, uptime monitoring, and system status
        - **Redis Operations:** Cache management, key statistics, and performance analytics
        
        ## 📊 Use Cases
        
        - **DevOps Monitoring:** Track system health and performance metrics
        - **Performance Optimization:** Analyze cache efficiency and response times
        - **System Maintenance:** Monitor Redis operations and system resources
        - **Health Checks:** Container orchestration and load balancer health verification
        
        ---
        
        **Part of the Market Data API Platform**
        """,
        "tags": utils_tags_metadata,
        "prefix": "/utils",
        "openapi_url": "/utils/openapi.json"
    },
    "market-data": {
        "title": "Market Data API",
        "description": """
        # 📊 Market Data API - Professional Financial Data Platform
        
        **Enterprise-grade market data API** providing real-time quotes, historical data, technical indicators, and comprehensive market intelligence.
        
        ## 🌟 Key Features
        
        - **📊 Real-time Quotes:** Live bid/ask prices, spreads, and market data
        - **📈 Historical Data:** OHLCV bars, technical indicators, and patterns
        - **📰 Financial News:** Real-time news with AI-ready content processing
        - **🔴 Live Streaming:** Server-Sent Events for real-time updates
        - **🧠 Market Intelligence:** Advanced analytics and comparative analysis
        - **⚡ High Performance:** Sub-100ms response times with intelligent caching
        
        ## 🎯 Use Cases
        
        - **Algorithmic Trading:** Real-time data feeds for trading algorithms
        - **Portfolio Management:** Live portfolio monitoring and analysis
        - **Research & Analysis:** Historical data for backtesting and research
        - **AI/ML Models:** Clean, structured data for machine learning
        - **Trading Platforms:** Data integration for custom trading applications
        - **Discord Bots:** Real-time market updates and alerts
        
        ## 🔌 Data Sources
        
        - **Alpaca Market Data:** Real-time quotes, bars, and news
        - **Benzinga News:** Financial news and market updates
        - **Redis Cache:** High-performance data caching
        - **Custom Analytics:** Advanced technical indicators and patterns
        
        ---
        
        **Professional Financial Data Platform**
        """,
        "tags": market_data_tags_metadata,
        "prefix": "/market-data",
        "openapi_url": "/market-data/openapi.json"
    }
}

def get_api_group_config(group_name: str) -> Dict:
    """Get configuration for a specific API group."""
    return API_GROUPS.get(group_name, {})

def get_all_api_groups() -> List[str]:
    """Get list of all available API group names."""
    return list(API_GROUPS.keys())

def create_api_group_app(group_name: str, base_app: FastAPI) -> FastAPI:
    """Create a FastAPI app for a specific API group."""
    config = get_api_group_config(group_name)
    if not config:
        raise ValueError(f"Unknown API group: {group_name}")
    
    app = FastAPI(
        title=config["title"],
        description=config["description"],
        version="1.0.0",
        docs_url=None,  # Disable docs for mounted apps
        redoc_url=None,  # Disable redoc for mounted apps
        openapi_url=config["openapi_url"],
    )
    
    # Set tags for this API group
    app.openapi = lambda: create_group_openapi(app, config["tags"])
    
    return app

def create_group_openapi(app: FastAPI, tags: List[Dict]) -> Dict:
    """Create OpenAPI schema for a specific API group."""
    from fastapi.openapi.utils import get_openapi
    from .contact import get_contact_info
    from .servers import get_servers
    
    if app.openapi_schema:
        return app.openapi_schema
    
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["tags"] = tags
    schema["info"].update(get_contact_info())
    schema["servers"] = get_servers()
    
    app.openapi_schema = schema
    return schema

def get_swagger_ui_parameters() -> Dict:
    """Get Swagger UI parameters configured for multiple API specifications."""
    return {
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
        # Multiple API specifications support
        "urls": [
            {
                "name": "Market Data API",
                "url": "/market-data/openapi.json"
            },
            {
                "name": "Utils API", 
                "url": "/utils/openapi.json"
            }
        ]
    }
