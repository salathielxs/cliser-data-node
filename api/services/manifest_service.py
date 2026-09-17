from __future__ import annotations

from typing import Any

from node.registry import get_manifest as registry_get_manifest


class ManifestServiceError(Exception):
    pass


def get_object_manifest(
    namespace: str,
    object_id: str,
) -> dict[str, Any]:
    manifest = registry_get_manifest(object_id)

    if manifest is None:
        raise ManifestServiceError("Manifest não encontrado")

    if manifest["namespace"] != namespace:
        raise ManifestServiceError("Manifest fora do namespace")

    if str(manifest.get("status", "")).upper() == "DELETED":
        raise ManifestServiceError("Manifest não encontrado")

    if manifest["status"] != "ACTIVE":
        raise ManifestServiceError("Manifest não está ativo")

    return {
        "object_id": manifest["object_id"],
        "namespace": manifest["namespace"],
        "total_size": manifest["total_size"],
        "block_size": manifest["block_size"],
        "block_count": manifest["block_count"],
        "created_at": manifest["created_at"],
        "status": manifest["status"],
        "blocks": [
            {
                "index": block["index"],
                "block_id": block["block_id"],
                "size": block["size"],
            }
            for block in manifest["blocks"]
        ],
    }
