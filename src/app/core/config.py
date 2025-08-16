import os
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field

from src.app.clients.alpaca_client import AlpacaClient
from src.app.services.prices_service import PricesService


class Settings(BaseSettings):
    # General app settings
    app_name: str = Field(default="market-data-api", alias="SERVICE_NAME")
    description: str = Field(default="A stateless micro‑service delivering your dreams.", alias="SERVICE_DESC")
    version: str = Field(default="0.1.0", alias="API_VER")
    port: int = Field(default=8000, alias="PORT")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    alpaca_streaming_enabled: bool = Field(default=True, alias="ALPACA_STREAMING_ENABLED", description="Enable real-time streaming")
    
    # Alpaca API settings
    alpaca_key_id: str = Field(..., alias="ALPACA_API_KEY", description="Alpaca API key ID")
    alpaca_secret_key: str = Field(..., alias="ALPACA_SECRET", description="Alpaca API secret key")
    alpaca_data_base_url: str = Field(default="https://data.alpaca.markets/v2", alias="ALPACA_BASE_URL")
    alpaca_feed: str = Field(default="iex", alias="ALPACA_FEED", description="Data feed type: iex (free) or sip (pro)")
    alpaca_timeout: float = Field(default=8.0, alias="ALPACA_TIMEOUT")

    class Config:
        env_file = ".env"
        extra = "ignore"  # optionally ignore unknown env vars


# Global instances
_settings: Optional[Settings] = None
_alpaca_client: Optional[AlpacaClient] = None


def get_settings() -> Settings:
    """Get or create the singleton Settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def get_alpaca_client() -> AlpacaClient:
    """Get or create the singleton AlpacaClient instance."""
    global _alpaca_client
    if _alpaca_client is None:
        settings = get_settings()
        _alpaca_client = AlpacaClient(
            alpaca_key_id=settings.alpaca_key_id,
            alpaca_secret_key=settings.alpaca_secret_key,
            alpaca_base_url=settings.alpaca_data_base_url,
            feed=settings.alpaca_feed,
            timeout=settings.alpaca_timeout,
        )
    return _alpaca_client


def get_alpaca() -> PricesService:
    """Get PricesService with singleton AlpacaClient."""
    return PricesService(alpaca_client=get_alpaca_client())


async def cleanup_alpaca_client():
    """Clean up the singleton AlpacaClient instance."""
    global _alpaca_client
    if _alpaca_client:
        await _alpaca_client.aclose()
        _alpaca_client = None
