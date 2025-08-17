from src.app.core.config import get_settings


def get_servers():
    """
    Dynamically generates server URLs based on the environment.
    """
    settings = get_settings()
    if settings.environment == "production":
        return [
            {"url": "https://market-data-api.vercel.app/", "description": "Production API - High availability, enterprise SLA"},
        ]
    elif settings.environment == "staging":
        return [
            {"url": "https://staging-api.marketdata.com", "description": "Staging Environment - Pre-production testing"},
            {"url": "https://staging-api-us-east.marketdata.com", "description": "US East Staging - Regional testing"}
        ]
    else:  # Default to development
        return [
            {"url": "http://localhost:8000", "description": "Local Development - Docker container"},
            {"url": "http://127.0.0.1:8000", "description": "Local Development - Alternative localhost"},
            {"url": "http://0.0.0.0:8000", "description": "Local Development - Network accessible"}
        ]
