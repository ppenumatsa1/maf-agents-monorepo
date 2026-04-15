from __future__ import annotations

import pytest

from app.core.security.dependencies import get_auth_config, get_token_validator


@pytest.fixture(autouse=True)
def clear_auth_dependency_caches() -> None:
    get_auth_config.cache_clear()
    get_token_validator.cache_clear()
    yield
    get_auth_config.cache_clear()
    get_token_validator.cache_clear()


@pytest.fixture
def set_auth_env(monkeypatch: pytest.MonkeyPatch):
    def _set(enabled: bool) -> None:
        monkeypatch.setenv("REQUIRE_AUTH", "true" if enabled else "false")
        monkeypatch.setenv("ENTRA_TENANT_ID", "tenant")
        monkeypatch.setenv("ENTRA_CLIENT_ID", "client-id")
        monkeypatch.setenv("ENTRA_AUDIENCE", "api://researcher-agent")

    return _set
