from __future__ import annotations

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PublicKey,
)

from node import crypto_identity
from node.access_control import (
    Principal,
    create_principal,
)
from node.registry import (
    get_peer_authorization_by_fingerprint,
)
from runtime.peer import CellEnvelope


class PeerAuthorizationError(PermissionError):
    """Erro de autenticação/autorização de uma identidade Cell."""


def _public_key_from_peer(envelope: CellEnvelope) -> Ed25519PublicKey:
    source = envelope.source

    if not source.public_key:
        raise PeerAuthorizationError(
            "Peer sem chave pública."
        )

    if not source.fingerprint:
        raise PeerAuthorizationError(
            "Peer sem fingerprint."
        )

    try:
        raw_key = base64.b64decode(
            source.public_key.encode("ascii"),
            validate=True,
        )
    except Exception as exc:
        raise PeerAuthorizationError(
            "Chave pública inválida."
        ) from exc

    if len(raw_key) != 32:
        raise PeerAuthorizationError(
            "Chave pública Ed25519 inválida."
        )

    try:
        public_key = Ed25519PublicKey.from_public_bytes(
            raw_key
        )
    except Exception as exc:
        raise PeerAuthorizationError(
            "Não foi possível reconstruir a chave pública."
        ) from exc

    computed_fingerprint = crypto_identity.fingerprint(
        public_key
    )

    if computed_fingerprint != source.fingerprint:
        raise PeerAuthorizationError(
            "Fingerprint da chave pública não confere."
        )

    return public_key


def resolve_principal_from_envelope(
    envelope: CellEnvelope,
) -> Principal:
    """
    Resolve a identidade autorizada de uma CellEnvelope.

    A identidade criptográfica da origem é determinada pela chave
    pública presente no PeerIdentity. A autorização RBAC é obtida
    exclusivamente do registro persistido peer_authorizations.

    source.role e request.identity_id não são utilizados como
    autoridade de autorização.
    """

    if not isinstance(envelope, CellEnvelope):
        raise TypeError(
            "envelope deve ser CellEnvelope."
        )

    envelope.validate()

    _public_key_from_peer(envelope)

    fingerprint = envelope.source.fingerprint

    authorization = get_peer_authorization_by_fingerprint(
        fingerprint
    )

    if authorization is None:
        raise PeerAuthorizationError(
            "Peer não autorizado: fingerprint não registrado."
        )

    if authorization["status"] != "ACTIVE":
        raise PeerAuthorizationError(
            "Peer não autorizado: autorização não está ACTIVE."
        )

    if authorization["fingerprint"] != fingerprint:
        raise PeerAuthorizationError(
            "Binding de fingerprint inválido."
        )

    authorized_namespace = authorization["namespace"]
    request_namespace = envelope.request.namespace

    if (
        authorized_namespace is not None
        and request_namespace != authorized_namespace
    ):
        raise PeerAuthorizationError(
            "Peer fora do escopo do namespace autorizado."
        )

    return create_principal(
        identity_id=authorization["identity_id"],
        role=authorization["role"],
        namespace=authorized_namespace,
    )
