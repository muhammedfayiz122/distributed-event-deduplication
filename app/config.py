from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application configuration settings."""

    app_name: str = "Distributed Event Deduplication"
    version: str = "0.1.0"
    debug: bool = True
    
@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

settings = get_settings()
