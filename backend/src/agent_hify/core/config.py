from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hify:hify@localhost:5432/hify"
    redis_url: str = "redis://localhost:6379/0"
    embedding_dim: int = 1536


@lru_cache
def get_settings() -> Settings:
    return Settings()
