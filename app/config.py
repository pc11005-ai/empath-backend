"""
Centralised app configuration.

All secrets (Supabase service key, Gemini API key) are read from environment
variables on the server only. They are never sent to, or read by, the
frontend in any way.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str

    gemini_api_key: str
    gemini_model: str = "gemini-3.7-flash"
    gemini_classifier_model: str = "gemini-3.5-flash-lite"

    cors_origins: str = "*"
    trash_retention_days: int = 30

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
