from __future__ import annotations

from typing import Any

from node.object_manager import put_object
from node.registry import get_object as registry_get_object


class UploadServiceError(Exception):
    pass


def upload_object(
    namespace: str,
    filename: str,
    data: bytes,
) -> dict[str, Any]:
    if not filename:
        raise UploadServiceError("Filename obrigatório")

    if not data:
        raise UploadServiceError("Arquivo vazio não permitido")

    try:
        result = put_object(
            data,
            namespace=namespace,
        )
    except Exception as exc:
        raise UploadServiceError(
            f"Falha ao armazenar upload: {exc}"
        ) from exc

    if isinstance(result, tuple) and len(result) == 2:
        object_id, status = result

        metadata = registry_get_object(object_id)

        if metadata is None:
            raise UploadServiceError(
                "Objeto criado mas não localizado no registry"
            )

        return {
            "object_id": object_id,
            "namespace": metadata["namespace"],
            "filename": filename,
            "size": metadata["size"],
            "content_hash": metadata["content_hash"],
            "status": str(status),
        }

    if isinstance(result, dict):
        return {
            "object_id": result["object_id"],
            "namespace": result["namespace"],
            "filename": filename,
            "size": result["size"],
            "content_hash": result["content_hash"],
            "status": result["status"],
        }

    raise UploadServiceError(
        "Retorno inesperado de node.object_manager.put_object"
    )
