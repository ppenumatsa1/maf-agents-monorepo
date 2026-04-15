from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import AuthConfig
from app.core.security.dependencies import get_current_principal, require_roles
from app.core.security.jwks import JwksCache
from app.core.security.models import Principal
from app.core.security.token_validator import TokenValidationError, TokenValidator


def _create_keypair() -> tuple[Any, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk["kid"] = "kid-1"
    return private_key, public_jwk


def _issue_token(private_key: Any, claims: dict[str, Any], kid: str = "kid-1") -> str:
    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": kid, "typ": "JWT"},
    )


def test_jwks_cache_uses_cached_keys() -> None:
    _, jwk = _create_keypair()
    calls = 0

    async def scenario() -> None:
        nonlocal calls

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                json={"keys": [jwk]},
                headers={"Cache-Control": "max-age=3600"},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            cache = JwksCache("https://example.test/keys", ttl_seconds=1, http_client=client)
            await cache.get_signing_key("kid-1")
            await cache.get_signing_key("kid-1")

    asyncio.run(scenario())

    assert calls == 1


def test_token_validator_accepts_valid_app_token() -> None:
    private_key, jwk = _create_keypair()
    now = int(time.time())
    token = _issue_token(
        private_key,
        {
            "iss": "https://login.microsoftonline.com/tenant/v2.0",
            "aud": "api://researcher-agent",
            "exp": now + 600,
            "nbf": now - 10,
            "appid": "client-id",
            "idtyp": "app",
            "roles": ["Research.Read"],
            "sub": "subject",
            "tid": "tenant",
        },
    )

    async def scenario() -> Principal:
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"keys": [jwks]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            config = AuthConfig(
                require_auth=True,
                tenant_id="tenant",
                client_id="client-id",
                audience="api://researcher-agent",
                authority="https://login.microsoftonline.com/tenant",
                issuer="https://login.microsoftonline.com/tenant/v2.0",
                jwks_url="https://example.test/keys",
                jwks_cache_ttl_seconds=300,
                allowed_algorithms=("RS256",),
            )
            validator = TokenValidator(
                config, jwks_cache=JwksCache(config.jwks_url, http_client=client)
            )
            return await validator.validate(token)

    jwks = jwk
    principal = asyncio.run(scenario())
    assert principal.authenticated is True
    assert principal.client_id == "client-id"
    assert "Research.Read" in principal.roles


def test_token_validator_rejects_invalid_audience() -> None:
    private_key, jwk = _create_keypair()
    now = int(time.time())
    token = _issue_token(
        private_key,
        {
            "iss": "https://login.microsoftonline.com/tenant/v2.0",
            "aud": "api://wrong-audience",
            "exp": now + 600,
            "appid": "client-id",
            "idtyp": "app",
        },
    )

    async def scenario() -> None:
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"keys": [jwk]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            config = AuthConfig(
                require_auth=True,
                tenant_id="tenant",
                client_id="client-id",
                audience="api://researcher-agent",
                authority="https://login.microsoftonline.com/tenant",
                issuer="https://login.microsoftonline.com/tenant/v2.0",
                jwks_url="https://example.test/keys",
                jwks_cache_ttl_seconds=300,
                allowed_algorithms=("RS256",),
            )
            validator = TokenValidator(
                config, jwks_cache=JwksCache(config.jwks_url, http_client=client)
            )
            with pytest.raises(TokenValidationError):
                await validator.validate(token)

    asyncio.run(scenario())


def test_get_current_principal_returns_anonymous_when_auth_disabled(set_auth_env) -> None:
    set_auth_env(False)
    principal = asyncio.run(get_current_principal(credentials=None))

    assert principal.authenticated is False
    assert principal.roles == set()


def test_get_current_principal_rejects_missing_token_when_auth_enabled(set_auth_env) -> None:
    set_auth_env(True)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_principal(credentials=None))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing bearer token"


def test_get_current_principal_rejects_invalid_token(
    set_auth_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_auth_env(True)

    class _BrokenValidator:
        async def validate(self, _token: str) -> Principal:
            raise TokenValidationError("invalid")

    monkeypatch.setattr(
        "app.core.security.dependencies.get_token_validator", lambda: _BrokenValidator()
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            get_current_principal(
                credentials=HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="bad-token",
                )
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid bearer token"


def test_require_roles_bypasses_validation_when_auth_disabled(set_auth_env) -> None:
    set_auth_env(False)
    dependency = require_roles("Research.Read")

    principal = asyncio.run(dependency(principal=Principal.anonymous()))

    assert principal.authenticated is False


def test_require_roles_returns_403_with_missing_roles(set_auth_env) -> None:
    set_auth_env(True)
    dependency = require_roles("Research.Read", "Research.Write")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            dependency(
                principal=Principal(
                    authenticated=True,
                    client_id="client-id",
                    roles={"Research.Read"},
                )
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Missing required roles: Research.Write"
