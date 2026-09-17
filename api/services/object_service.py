from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from api.config import MAX_OBJECT_SIZE_BYTES

from node.object_manager import (
    put_object,
    get_object_data,
    verify_object,
    delete_object_data,
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyReplayError,
)
from node.registry import (
    get_object as registry_get_object,
    list_objects as registry_list_objects,
)


class ObjectServiceError(Exception):
    pass


def _decode_data(data: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except Exception as exc:
        raise ObjectServiceError(
            "Campo data deve conter Base64 válido"
        ) from exc


def create_object(
    namespace: str,
    data: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    raw = _decode_data(data)

    if len(raw) > MAX_OBJECT_SIZE_BYTES:
        raise ObjectServiceError(
            "Objeto excede o limite máximo permitido"
        )

    request_fingerprint = None

    if idempotency_key is not None:
        idempotency_key = idempotency_key.strip()

        if not idempotency_key:
            raise ObjectServiceError(
                "Idempotency-Key não pode ser vazia"
            )

        # Fingerprint canônico:
        # - operação
        # - namespace
        # - hash do conteúdo
        #
        # O conteúdo bruto nunca é armazenado como fingerprint.

        fingerprint_payload = {
            "operation": "PUT",
            "namespace": namespace,
            "data_sha256": hashlib.sha256(raw).hexdigest(),
        }

        canonical = json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        request_fingerprint = hashlib.sha256(
            canonical
        ).hexdigest()

    try:
        result = put_object(
            raw,
            namespace=namespace,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )

    except (
        IdempotencyConflictError,
        IdempotencyInProgressError,
        IdempotencyReplayError,
    ):
        raise

    except (
        ValueError,
        PermissionError,
        TypeError,
    ) as exc:
        raise ObjectServiceError(str(exc)) from exc

    if isinstance(result, dict):
        return result

    if isinstance(result, tuple):
        if len(result) == 2:
            object_id, status = result
            metadata = registry_get_object(object_id)

            if metadata is None:
                raise ObjectServiceError(
                    "Objeto criado mas não localizado no registry"
                )

            return {
                "object_id": object_id,
                "namespace": metadata["namespace"],
                "size": metadata["size"],
                "content_hash": metadata["content_hash"],
                "status": str(status),
            }

    raise ObjectServiceError(
        "Retorno inesperado de node.object_manager.put_object"
    )


def get_object(
    namespace: str,
    object_id: str,
) -> dict[str, Any]:
    metadata = registry_get_object(object_id)

    if metadata is None:
        raise ObjectServiceError("Objeto não encontrado")

    if metadata["namespace"] != namespace:
        raise ObjectServiceError("Objeto fora do namespace")

    if str(metadata.get("status", "")).upper() == "DELETED":
        raise ObjectServiceError("Objeto não encontrado")

    return metadata


def verify_object_service(
    namespace: str,
    object_id: str,
) -> dict[str, Any]:
    metadata = registry_get_object(object_id)

    if metadata is None:
        raise ObjectServiceError("Objeto não encontrado")

    if metadata["namespace"] != namespace:
        raise ObjectServiceError("Objeto fora do namespace")

    if str(metadata.get("status", "")).upper() == "DELETED":
        raise ObjectServiceError("Objeto não encontrado")

    valid, status = verify_object(object_id)

    return {
        "object_id": object_id,
        "valid": bool(valid),
        "status": str(status),
        "message": str(status),
    }


def delete_object(
    namespace: str,
    object_id: str,
) -> dict[str, Any]:
    metadata = registry_get_object(object_id)

    if metadata is None:
        raise ObjectServiceError("Objeto não encontrado")

    if metadata["namespace"] != namespace:
        raise ObjectServiceError("Objeto fora do namespace")

    deleted, status = delete_object_data(object_id)

    return {
        "object_id": object_id,
        "deleted": bool(deleted),
        "status": str(status),
    }


def list_namespace_objects(namespace: str) -> list[dict[str, Any]]:
    objects = registry_list_objects(namespace=namespace)

    result: list[dict[str, Any]] = []

    for row in objects:
        # Registry retorna:
        # (object_id, size, namespace, created_at, status)
        object_id, size, row_namespace, created_at, status = row

        result.append(
            {
                "object_id": object_id,
                "namespace": row_namespace,
                "size": size,
                "created_at": created_at,
                "status": status,
            }
        )

    return result


def read_object_data(
    namespace: str,
    object_id: str,
) -> bytes:
    metadata = registry_get_object(object_id)

    if metadata is None:
        raise ObjectServiceError("Objeto não encontrado")

    if metadata["namespace"] != namespace:
        raise ObjectServiceError("Objeto fora do namespace")

    if str(metadata.get("status", "")).upper() == "DELETED":
        raise ObjectServiceError("Objeto não encontrado")

    return get_object_data(object_id)
