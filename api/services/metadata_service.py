from __future__ import annotations

from node.registry import get_object as registry_get_object


class MetadataServiceError(Exception):
    pass


def get_object_metadata(namespace: str, object_id: str) -> dict:
    metadata = registry_get_object(object_id)

    if metadata is None:
        raise MetadataServiceError("Objeto não encontrado")

    if metadata["namespace"] != namespace:
        raise MetadataServiceError("Objeto fora do namespace")

    if str(metadata.get("status", "")).upper() == "DELETED":
        raise MetadataServiceError("Objeto não encontrado")

    return {
        "object_id": metadata["object_id"],
        "namespace": metadata["namespace"],
        "size": metadata["size"],
        "content_hash": metadata["content_hash"],
        "created_at": metadata.get("created_at"),
        "status": metadata["status"],
    }
