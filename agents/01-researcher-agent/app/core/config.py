import os
from dataclasses import dataclass


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MAFConfig:
    provider: str
    model: str
    foundry_projects_endpoint: str | None
    foundry_model_deployment_name: str | None

    @staticmethod
    def from_env() -> "MAFConfig":
        provider = os.getenv("MAF_PROVIDER", "foundry").lower()
        if provider not in {"azure", "azure_openai", "foundry", "azure_ai"}:
            provider = "foundry"
        model = os.getenv("MAF_MODEL", "gpt-4o-mini")

        return MAFConfig(
            provider=provider,
            model=model,
            foundry_projects_endpoint=os.getenv("FOUNDRY_PROJECTS_ENDPOINT"),
            foundry_model_deployment_name=os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME"),
        )


@dataclass(frozen=True)
class AuthConfig:
    require_auth: bool
    tenant_id: str | None
    client_id: str | None
    audience: str | None
    authority: str | None
    issuer: str | None
    jwks_url: str
    jwks_cache_ttl_seconds: int
    allowed_algorithms: tuple[str, ...]

    @staticmethod
    def from_env() -> "AuthConfig":
        require_auth = _to_bool(os.getenv("REQUIRE_AUTH"), default=False)
        tenant_id = os.getenv("ENTRA_TENANT_ID")
        client_id = os.getenv("ENTRA_CLIENT_ID")

        authority = os.getenv("ENTRA_AUTHORITY")
        if not authority and tenant_id:
            authority = f"https://login.microsoftonline.com/{tenant_id}"

        issuer = os.getenv("ENTRA_ISSUER")
        if not issuer and authority:
            issuer = f"{authority}/v2.0"

        audience = os.getenv("ENTRA_AUDIENCE") or client_id

        jwks_url = os.getenv("ENTRA_JWKS_URL")
        if not jwks_url and authority:
            jwks_url = f"{authority}/discovery/v2.0/keys"

        if require_auth:
            missing = []
            if not tenant_id:
                missing.append("ENTRA_TENANT_ID")
            if not client_id:
                missing.append("ENTRA_CLIENT_ID")
            if not audience:
                missing.append("ENTRA_AUDIENCE (or ENTRA_CLIENT_ID)")
            if not issuer:
                missing.append("ENTRA_ISSUER (or ENTRA_TENANT_ID)")
            if not jwks_url:
                missing.append("ENTRA_JWKS_URL (or ENTRA_TENANT_ID)")
            if missing:
                raise ValueError(
                    "REQUIRE_AUTH=true but missing auth settings: " + ", ".join(missing)
                )

        resolved_jwks_url = (
            jwks_url or "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        )

        return AuthConfig(
            require_auth=require_auth,
            tenant_id=tenant_id,
            client_id=client_id,
            audience=audience,
            authority=authority,
            issuer=issuer,
            jwks_url=resolved_jwks_url,
            jwks_cache_ttl_seconds=int(os.getenv("ENTRA_JWKS_CACHE_TTL_SECONDS", "300")),
            allowed_algorithms=("RS256",),
        )
