from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Principal(BaseModel):
    authenticated: bool = False
    subject: str | None = None
    tenant_id: str | None = None
    client_id: str | None = None
    roles: set[str] = Field(default_factory=set)
    claims: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def anonymous(cls) -> "Principal":
        return cls(authenticated=False)

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> "Principal":
        roles_claim = claims.get("roles") or []
        if isinstance(roles_claim, str):
            roles = {roles_claim}
        elif isinstance(roles_claim, list):
            roles = {role for role in roles_claim if isinstance(role, str)}
        else:
            roles = set()

        return cls(
            authenticated=True,
            subject=claims.get("sub"),
            tenant_id=claims.get("tid"),
            client_id=claims.get("azp") or claims.get("appid"),
            roles=roles,
            claims=claims,
        )
