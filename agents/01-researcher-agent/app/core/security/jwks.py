from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class JwksCache:
    def __init__(
        self,
        jwks_url: str,
        *,
        ttl_seconds: int = 300,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._jwks_url = jwks_url
        self._ttl_seconds = ttl_seconds
        self._http_client = http_client
        self._keys_by_kid: dict[str, dict[str, Any]] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get_signing_key(self, kid: str) -> dict[str, Any]:
        if not kid:
            raise ValueError("Token is missing key id (kid)")

        await self._refresh_if_needed()
        key = self._keys_by_kid.get(kid)
        if key:
            return key

        await self._refresh_if_needed(force=True)
        key = self._keys_by_kid.get(kid)
        if key:
            return key

        raise ValueError("Unable to find signing key for token kid")

    async def _refresh_if_needed(self, *, force: bool = False) -> None:
        now = time.time()
        if not force and self._keys_by_kid and now < self._expires_at:
            return

        async with self._lock:
            now = time.time()
            if not force and self._keys_by_kid and now < self._expires_at:
                return

            response = await self._request_jwks()
            response.raise_for_status()
            body = response.json()

            keys = body.get("keys")
            if not isinstance(keys, list):
                raise ValueError("JWKS payload did not contain a keys list")

            mapped: dict[str, dict[str, Any]] = {}
            for key in keys:
                kid = key.get("kid") if isinstance(key, dict) else None
                if kid:
                    mapped[kid] = key

            if not mapped:
                raise ValueError("JWKS payload contained no valid signing keys")

            self._keys_by_kid = mapped
            max_age = _parse_max_age(response.headers.get("cache-control"), self._ttl_seconds)
            self._expires_at = time.time() + max_age

    async def _request_jwks(self) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(self._jwks_url)

        async with httpx.AsyncClient(timeout=10.0) as client:
            return await client.get(self._jwks_url)


def _parse_max_age(cache_control: str | None, default_ttl: int) -> int:
    if not cache_control:
        return default_ttl

    for directive in cache_control.split(","):
        candidate = directive.strip().lower()
        if candidate.startswith("max-age="):
            _, value = candidate.split("=", 1)
            if value.isdigit():
                return max(int(value), 1)

    return default_ttl
