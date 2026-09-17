from __future__ import annotations

from node.object_manager import get_object_data
from node.registry import get_object as registry_get_object


class DownloadServiceError(Exception):
    pass


class DownloadObjectDeletedError(DownloadServiceError):
    """Objeto existe, mas foi removido logicamente."""
    pass


def download_object(namespace: str, object_id: str) -> tuple[bytes, dict]:
    metadata = registry_get_object(object_id)

    if metadata is None:
        raise DownloadServiceError("Objeto não encontrado")

    if metadata["namespace"] != namespace:
        raise DownloadServiceError("Objeto fora do namespace")

    status = str(metadata.get("status", "")).upper()

    if status == "DELETED":
        raise DownloadObjectDeletedError("Objeto não encontrado")

    if status != "ACTIVE":
        raise DownloadServiceError(
            f"Objeto não está disponível para download: {status or 'UNKNOWN'}"
        )

    try:
        data = get_object_data(object_id)
    except Exception as exc:
        raise DownloadServiceError(
            f"Falha ao recuperar objeto: {exc}"
        ) from exc

    if len(data) != metadata["size"]:
        raise DownloadServiceError(
            "Integridade inválida: tamanho divergente"
        )

    return data, metadata
