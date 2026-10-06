"""Application configuration.

Settings are read from environment variables (see .env.example / docker-compose.yml).
No secret ever has a hardcoded fallback value in a way that would be safe for
production: SESSION_SECRET_KEY must be supplied explicitly outside of local
development.
"""
from __future__ import annotations

import os
from functools import lru_cache

_LOCAL_DEV_DEFAULT_SECRET = "dev-only-insecure-secret-change-me"


class Settings:
    """Simple environment-backed settings container.

    We intentionally avoid pulling in pydantic-settings for this small
    surface area; plain env var reads keep the dependency footprint small
    while still being explicit about required vs. optional values.
    """

    def __init__(self) -> None:
        raw_database_url = os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg://lifehub:lifehub@localhost:5432/lifehub",
        )
        # Managed hosts (Render, Railway, etc.) hand out connection strings
        # with the bare "postgres://" or "postgresql://" scheme, which
        # SQLAlchemy resolves to psycopg2 by default. We ship psycopg (v3)
        # instead, so normalize the scheme to request that driver explicitly.
        if raw_database_url.startswith("postgres://"):
            raw_database_url = raw_database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif raw_database_url.startswith("postgresql://") and not raw_database_url.startswith("postgresql+psycopg://"):
            raw_database_url = raw_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.database_url: str = raw_database_url

        self.environment: str = os.environ.get("ENVIRONMENT", "development")
        self.is_production: bool = self.environment.lower() == "production"

        secret = os.environ.get("SESSION_SECRET_KEY")
        if not secret:
            if self.is_production:
                raise RuntimeError(
                    "SESSION_SECRET_KEY must be set explicitly when ENVIRONMENT=production. "
                    "Refusing to start with a placeholder secret."
                )
            secret = _LOCAL_DEV_DEFAULT_SECRET
        self.session_secret_key: str = secret

        self.session_cookie_name: str = os.environ.get("SESSION_COOKIE_NAME", "lifehub_session")
        self.session_ttl_hours: int = int(os.environ.get("SESSION_TTL_HOURS", "720"))  # 30 days

        # Password policy: deliberately simple (2-user household, no self-service
        # signup), but a minimum length is enforced to avoid the "no password
        # policy at all" weakness identified in the KitchenOwl review.
        self.min_password_length: int = int(os.environ.get("MIN_PASSWORD_LENGTH", "10"))

        # CORS origins for the PWA frontend, comma separated.
        origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
        self.cors_origins: list[str] = [o.strip() for o in origins.split(",") if o.strip()]

        # KitchenOwl adapter configuration (optional; the integration is a
        # separate module that can be wired up later per the project brief).
        self.kitchenowl_base_url: str | None = os.environ.get("KITCHENOWL_BASE_URL")
        self.kitchenowl_username: str | None = os.environ.get("KITCHENOWL_USERNAME")
        self.kitchenowl_password: str | None = os.environ.get("KITCHENOWL_PASSWORD")
        self.kitchenowl_household_id: str | None = os.environ.get("KITCHENOWL_HOUSEHOLD_ID")

        # Meal-assistant integration: lets a user discuss a dish/meal with an
        # LLM and have the ingredients it settles on pushed straight to the
        # KitchenOwl shopping list. Uses any OpenAI-compatible chat
        # completions API (OpenAI itself, Azure OpenAI via a compatible
        # proxy, a local model server, etc.) so the provider is swappable via
        # env vars alone; no provider SDK is hard-wired into the app.
        self.assistant_api_key: str | None = os.environ.get("ASSISTANT_API_KEY")
        self.assistant_base_url: str = os.environ.get(
            "ASSISTANT_BASE_URL", "https://api.openai.com/v1"
        )
        self.assistant_model: str = os.environ.get("ASSISTANT_MODEL", "gpt-4o-mini")


@lru_cache
def get_settings() -> Settings:
    return Settings()
