from __future__ import annotations

from dataclasses import dataclass

from api.auth import AuthenticatedPrincipal
from api.config import (
    RATE_LIMIT_READ_PER_MINUTE,
    RATE_LIMIT_WRITE_METHODS,
    RATE_LIMIT_WRITE_PER_MINUTE,
    RATE_LIMIT_WINDOW_SECONDS,
)


@dataclass(frozen=True)
class RateLimitPolicy:
    operation: str
    limit: int
    window_seconds: int


def get_rate_limit_policy(
    method: str,
) -> RateLimitPolicy:

    method = method.upper()

    if method in RATE_LIMIT_WRITE_METHODS:
        return RateLimitPolicy(
            operation="WRITE",
            limit=RATE_LIMIT_WRITE_PER_MINUTE,
            window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        )

    return RateLimitPolicy(
        operation="READ",
        limit=RATE_LIMIT_READ_PER_MINUTE,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )


def build_rate_limit_key(
    principal: AuthenticatedPrincipal,
) -> str:
    identity_id = principal.identity_id
    credential_id = principal.credential_id or "none"
    namespace = principal.namespace or "*"

    return (
        f"identity:{identity_id}"
        f"|credential:{credential_id}"
        f"|namespace:{namespace}"
    )


def build_identity_rate_limit_key(
    principal: AuthenticatedPrincipal,
) -> str:
    return f"identity-global:{principal.identity_id}"
