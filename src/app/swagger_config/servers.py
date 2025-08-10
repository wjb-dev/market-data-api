from src.app.core.config import settings


def get_servers():
    """
    Dynamically generates server URLs based on the environment.
    """
    if settings.environment == "production":
        return [{"url": "https://example.com", "description": "Production"}]
    elif settings.environment == "staging":
        return [{"url": "https://staging.example.com", "description": "Staging"}]
    else:  # Default to development
        return [{"url": "http://localhost:8000", "description": "Development"}]
