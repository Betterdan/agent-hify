from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://hify:hify@localhost:5432/hify"
    redis_url: str = "redis://localhost:6379/0"
    embedding_dim: int = 1536

    # 32 字节 url-safe base64 密钥（Fernet）；生产用环境变量覆盖
    encryption_key: str = "YWdlbnQtaGlmeS1kZXYtZmVybmV0LWtleS0zMmJ5dGU="
    secret_key: str = "dev-secret-hify-jwt-key-32bytes!"
    access_token_expire_minutes: int = 1440


@lru_cache
def get_settings() -> Settings:
    return Settings()
