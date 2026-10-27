import pytest
from pydantic import ValidationError

from lumiant.core.config import AppEnv, AuthMode, Settings


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[call-arg]


def test_development_defaults_enable_dev_auth() -> None:
    s = make()
    assert s.app_env is AppEnv.DEVELOPMENT
    assert s.dev_auth_enabled


@pytest.mark.security
def test_dev_auth_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="Development authentication cannot be enabled"):
        make(app_env="production", auth_mode="dev", cookie_secure=True)


@pytest.mark.security
def test_production_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        make(app_env="production", auth_mode="oidc", cookie_secure=False)


def test_production_with_oidc_and_secure_cookie_is_valid_config() -> None:
    s = make(app_env="production", auth_mode="oidc", cookie_secure=True)
    assert s.auth_mode is AuthMode.OIDC
    assert not s.dev_auth_enabled


@pytest.mark.security
def test_short_dev_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        make(dev_jwt_secret="too-short")


def test_env_prefix_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMIANT_APP_ENV", "test")
    monkeypatch.setenv("LUMIANT_SESSION_TTL_MINUTES", "60")
    s = make()
    assert s.app_env is AppEnv.TEST
    assert s.session_ttl_minutes == 60
