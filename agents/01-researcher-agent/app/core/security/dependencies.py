from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import AuthConfig
from app.core.observability.telemetry import record_auth_outcome
from app.core.security.models import Principal
from app.core.security.token_validator import TokenValidationError, TokenValidator

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_auth_config() -> AuthConfig:
    return AuthConfig.from_env()


@lru_cache(maxsize=1)
def get_token_validator() -> TokenValidator:
    config = get_auth_config()
    return TokenValidator(config)


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    config = get_auth_config()
    if not config.require_auth:
        record_auth_outcome(integration="entra_jwt", success=True, reason="auth_disabled")
        return Principal.anonymous()

    if credentials is None or credentials.scheme.lower() != "bearer":
        record_auth_outcome(integration="entra_jwt", success=False, reason="missing_bearer_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    validator = get_token_validator()
    try:
        principal = await validator.validate(credentials.credentials)
        record_auth_outcome(
            integration="entra_jwt",
            success=True,
            attributes={"principal.authenticated": principal.authenticated},
        )
        return principal
    except TokenValidationError as exc:
        record_auth_outcome(integration="entra_jwt", success=False, reason=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        ) from exc


def require_roles(*roles: str):
    async def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        config = get_auth_config()
        if not config.require_auth:
            return principal

        missing_roles = [role for role in roles if role not in principal.roles]
        if missing_roles:
            record_auth_outcome(
                integration="entra_jwt",
                success=False,
                reason="missing_required_roles",
                attributes={"missing_roles.count": len(missing_roles)},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required roles: {', '.join(missing_roles)}",
            )

        record_auth_outcome(
            integration="entra_jwt",
            success=True,
            attributes={"required_roles.count": len(roles)},
        )
        return principal

    return dependency
