from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # General app settings
    app_name: str = Field(default="market-data-api", env="SERVICE_NAME")
    description: str = Field(default="A stateless micro‑service delivering your dreams.", env="SERVICE_DESC")
    version: str = Field(default="0.1.0", env="API_VER")
    port: int = Field(default=8000, env="PORT")
    environment: str = Field(default="development", env="ENVIRONMENT")

    

    class Config:
        env_file = ".env"
        extra = "ignore"  # optionally ignore unknown env vars


# Global instance
settings = Settings()
