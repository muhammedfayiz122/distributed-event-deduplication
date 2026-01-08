from uuid import uuid4
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

class Settings(BaseSettings):
    """Application configuration settings."""

    app_name: str = "Distributed Event Deduplication"
    version: str = "0.1.0"
    debug: bool = True
    
    log_format: str = Field(default="json")  # Options: "json" or "console"
    
    instance_id: str = str(uuid4())
    dedup_ttl_seconds: int = 300  # Time-to-live for deduplication keys in seconds
    
    # Database settings
    database_url: str = Field(default="postgresql+asyncpg://postgres:123@localhost:5432/shipment_tracker_02")
    
    # Redis settings
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    class Config:
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = "utf-8"
        extra = "allow"
    
@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

settings = get_settings()
