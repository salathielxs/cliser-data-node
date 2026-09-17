from __future__ import annotations

import base64
import hashlib
import json

from node import crypto_identity


SIGNED_FIELDS = (
    "object_id",
    "namespace",
    "content_hash",
    "size",
)


def canonical_payload(
    object_id: str,
    namespace: str,
    content_hash: str,
    size: int,
) -> bytes:
    payload = {
        "content_hash": content_hash,
        "namespace": namespace,
        "object_id": object_id,
        "size": int(size),
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def object_digest(
    object_id: str,
    namespace: str,
    content_hash: str,
    size: int,
) -> str:
    payload = canonical_payload(
        object_id=object_id,
        namespace=namespace,
        content_hash=content_hash,
        size=size,
    )

    return hashlib.sha256(payload).hexdigest()


def sign_object(
    object_id: str,
    namespace: str,
    content_hash: str,
    size: int,
) -> dict:
    payload = canonical_payload(
        object_id=object_id,
        namespace=namespace,
        content_hash=content_hash,
        size=size,
    )

    signature = crypto_identity.sign(payload)

    identity = crypto_identity.load_identity()

    return {
        "signature_version": 1,
        "algorithm": "Ed25519",
        "signer_identity": identity["identity_id"],
        "signer_fingerprint": identity["fingerprint"],
        "payload_digest": hashlib.sha256(payload).hexdigest(),
        "signature": base64.b64encode(signature).decode("ascii"),
    }


def verify_object(
    object_id: str,
    namespace: str,
    content_hash: str,
    size: int,
    signature_record: dict,
) -> bool:
    if signature_record.get("algorithm") != "Ed25519":
        return False

    if signature_record.get("signature_version") != 1:
        return False

    payload = canonical_payload(
        object_id=object_id,
        namespace=namespace,
        content_hash=content_hash,
        size=size,
    )

    payload_digest = hashlib.sha256(payload).hexdigest()

    if payload_digest != signature_record.get("payload_digest"):
        return False

    try:
        signature = base64.b64decode(
            signature_record["signature"]
        )
    except Exception:
        return False

    return crypto_identity.verify(
        payload,
        signature,
    )
