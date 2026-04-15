from __future__ import annotations

import json

import jwt
from jwt import InvalidTokenError

from app.core.config import AuthConfig
from app.core.security.jwks import JwksCache
from app.core.security.models import Principal


class TokenValidationError(Exception):
    pass


class TokenValidator:
    def __init__(self, config: AuthConfig, jwks_cache: JwksCache | None = None) -> None:
        self._config = config
        self._jwks_cache = jwks_cache or JwksCache(
            config.jwks_url,
            ttl_seconds=config.jwks_cache_ttl_seconds,
        )

    async def validate(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm not in self._config.allowed_algorithms:
                raise TokenValidationError("Token signed with unsupported algorithm")

            kid = header.get("kid")
            if not isinstance(kid, str):
                raise TokenValidationError("Token header missing kid")

            jwk = await self._jwks_cache.get_signing_key(kid)
            key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(self._config.allowed_algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={"require": ["exp", "iss", "aud"]},
            )
            self._validate_app_only_claims(claims)
            return Principal.from_claims(claims)
        except (InvalidTokenError, ValueError) as exc:
            raise TokenValidationError(str(exc)) from exc

    @staticmethod
    def _validate_app_only_claims(claims: dict[str, object]) -> None:
        idtyp = claims.get("idtyp")
        if isinstance(idtyp, str) and idtyp != "app":
            raise TokenValidationError("Only app-only Entra tokens are accepted")

        if not claims.get("appid") and not claims.get("azp"):
            raise TokenValidationError("Token is missing app identifier claims")
