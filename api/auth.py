from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException

from node.registry import get_api_credential_by_hash


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    identity_id: str
    role: str
    namespace: Optional[str] = None
    credential_id: Optional[str] = None


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REQUIRED",
                "message": "Authorization header required",
            },
        )

    scheme, separator, credentials = authorization.partition(" ")

    if (
        not separator
        or scheme.lower() != "bearer"
        or not credentials.strip()
    ):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_INVALID",
                "message": "Invalid bearer authorization",
            },
        )

    return credentials.strip()


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_optional_principal(
    authorization: Optional[str],
) -> Optional[AuthenticatedPrincipal]:
    """
    Resolve o principal quando existe uma credencial válida.

    Não lança erro para credenciais ausentes ou inválidas.
    Isso permite que o rate limiter opere antes das
    dependências normais de autenticação.

    A autenticação definitiva continua sendo responsabilidade
    de get_current_principal().
    """

    if not authorization:
        return None

    try:
        token = extract_bearer_token(authorization)
    except HTTPException:
        return None

    token_hash = hash_token(token)
    credential = get_api_credential_by_hash(token_hash)

    if credential is None:
        return None

    if credential["status"] != "ACTIVE":
        return None

    return AuthenticatedPrincipal(
        identity_id=credential["identity_id"],
        role=credential["role"],
        namespace=credential["namespace"],
        credential_id=credential["credential_id"],
    )


async def get_current_principal(
    authorization: Optional[str] = Header(default=None),
) -> AuthenticatedPrincipal:

    token = extract_bearer_token(authorization)

    token_hash = hash_token(token)

    credential = get_api_credential_by_hash(token_hash)

    if credential is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_INVALID",
                "message": "Invalid credential",
            },
        )

    if credential["status"] != "ACTIVE":
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_REVOKED",
                "message": "Credential is not active",
            },
        )

    return AuthenticatedPrincipal(
        identity_id=credential["identity_id"],
        role=credential["role"],
        namespace=credential["namespace"],
        credential_id=credential["credential_id"],
    )
