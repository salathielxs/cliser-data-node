from __future__ import annotations

import hashlib
import secrets
from typing import Any

from node.registry import (
    register_api_credential,
    revoke_api_credential,
    list_api_credentials,
)


VALID_ROLES = {
    "READER",
    "WRITER",
    "ADMIN",
    "OWNER",
}


class CredentialError(Exception):
    pass


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def generate_token() -> str:
    """
    Gera um token criptograficamente seguro.

    O token bruto existe somente na memória e deve
    ser entregue ao operador uma única vez.
    """
    return secrets.token_urlsafe(48)


def create_api_credential(
    credential_id: str,
    identity_id: str,
    role: str,
    namespace: str | None = None,
) -> dict[str, Any]:
    if not credential_id:
        raise CredentialError(
            "credential_id obrigatório"
        )

    if not identity_id:
        raise CredentialError(
            "identity_id obrigatório"
        )

    role = role.upper()

    if role not in VALID_ROLES:
        raise CredentialError(
            f"Role inválida: {role}"
        )

    token = generate_token()
    token_hash = hash_token(token)

    try:
        register_api_credential(
            credential_id=credential_id,
            token_hash=token_hash,
            identity_id=identity_id,
            role=role,
            namespace=namespace,
            status="ACTIVE",
        )
    except Exception as exc:
        raise CredentialError(
            "Não foi possível registrar a credencial"
        ) from exc

    return {
        "credential_id": credential_id,
        "identity_id": identity_id,
        "role": role,
        "namespace": namespace,
        "status": "ACTIVE",
        "token": token,
    }


def revoke_api_credential_by_id(
    credential_id: str,
) -> bool:
    return revoke_api_credential(
        credential_id
    )


def list_credentials() -> list[dict[str, Any]]:
    return list_api_credentials()
