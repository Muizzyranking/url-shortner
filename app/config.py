from functools import cached_property
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "URL Shortener"
    ENVIRONMENT: str = Field(default="development")
    PORT: int = Field(default=8080)

    DATABASE_URL: str = Field(..., alias="DATABASE_URL")

    # Redis
    REDIS_URL: str = Field(..., alias="REDIS_URL")

    # Slugs / links
    SLUG_LENGTH: int = Field(default=7)
    BASE_REDIRECT_URL: str = Field(
        default="http://localhost:8080",
        description="Public base URL used when returning short links to clients.",
    )

    @computed_field
    @cached_property
    def DB_URL(self) -> str:
        url = self.DATABASE_URL

        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://"):
            if url.startswith(prefix):
                url = url.replace(prefix, "postgresql+asyncpg://", 1)
                break
        else:
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        parts = urlsplit(url)
        query = parse_qs(parts.query)
        query.pop("sslmode", None)
        query.pop("channel_binding", None)
        new_query = urlencode(query, doseq=True)
        url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
        )

        return url

    @computed_field
    @cached_property
    def SSL_REQUIRED(self) -> bool:
        """Whether the original DATABASE_URL requested sslmode=require (or similar)."""
        parts = urlsplit(self.DATABASE_URL)
        query = parse_qs(parts.query)
        sslmode = (query.get("sslmode") or [""])[0].lower()
        return sslmode in ("require", "verify-ca", "verify-full")


settings = Settings()
