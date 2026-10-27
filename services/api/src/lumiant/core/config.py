"""Application settings with fail-fast validation (ADR-0004)."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# services/api — config/, data/, var/ and alembic/ are resolved against this directory.
BASE_DIR = Path(__file__).resolve().parents[3]


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AuthMode(StrEnum):
    DEV = "dev"
    OIDC = "oidc"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LUMIANT_", env_file=BASE_DIR / ".env", extra="ignore", frozen=True)

    app_env: AppEnv = AppEnv.DEVELOPMENT
    auth_mode: AuthMode = AuthMode.DEV
    dev_jwt_secret: SecretStr | None = None
    session_ttl_minutes: int = Field(default=480, ge=5, le=1440)
    cookie_secure: bool = False
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR)$")
    tenant_config_dir: Path = BASE_DIR / "config" / "tenants"
    data_dir: Path = BASE_DIR
    app_db_url: str = f"sqlite:///{(BASE_DIR / 'var' / 'app.db').as_posix()}"
    auto_migrate: bool = True
    agent_provider: Literal["rules", "anthropic"] = "rules"
    agent_model: str = "claude-opus-5-5"
    anthropic_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.app_env is AppEnv.PRODUCTION:
            if self.auth_mode is AuthMode.DEV:
                raise ValueError("Development authentication cannot be enabled when LUMIANT_APP_ENV=production")
            if not self.cookie_secure:
                raise ValueError("LUMIANT_COOKIE_SECURE must be true when LUMIANT_APP_ENV=production")
        if self.dev_jwt_secret is not None and len(self.dev_jwt_secret.get_secret_value()) < 32:
            raise ValueError("LUMIANT_DEV_JWT_SECRET must be at least 32 characters")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION

    @property
    def dev_auth_enabled(self) -> bool:
        return self.auth_mode is AuthMode.DEV and not self.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
