from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_namespace_permission
from api.errors import APIError
from api.services import download_service
from api.services.download_service import DownloadObjectDeletedError


router = APIRouter(
    prefix="/api/v1/namespaces/{namespace}/objects",
    tags=["download"],
)


@router.get("/{object_id}/download")
async def download_object(
    namespace: str,
    object_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.read")
    ),
):
    try:
        data, metadata = download_service.download_object(
            namespace=namespace,
            object_id=object_id,
        )

        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Length": str(len(data)),
                "X-Object-ID": object_id,
                "X-Content-Hash": metadata["content_hash"],
            },
        )

    except DownloadObjectDeletedError as exc:
        raise APIError(
            code="OBJECT_NOT_FOUND",
            message="Objeto não encontrado",
            status_code=404,
        ) from exc

    except download_service.DownloadServiceError as exc:
        message = str(exc)
        message_lower = message.lower()

        # ----------------------------------------------------
        # Objeto removido / soft-deleted
        # ----------------------------------------------------
        #
        # O serviço pode produzir mensagens diferentes conforme
        # o caminho interno utilizado. Portanto, tratamos tanto
        # marcadores semânticos quanto referências ao estado.
        #
        deleted_markers = (
            "deleted",
            "deletado",
            "deletada",
            "marcado como deletado",
            "marcada como deletada",
            "objeto removido",
            "objeto excluído",
            "objeto excluido",
            "status=deleted",
            "status: deleted",
            "state=deleted",
            "state: deleted",
        )

        not_found_markers = (
            "não encontrado",
            "nao encontrado",
            "not found",
            "object not found",
        )

        namespace_markers = (
            "fora do namespace",
            "outro namespace",
            "namespace mismatch",
        )

        if (
            any(marker in message_lower for marker in deleted_markers)
            or any(marker in message_lower for marker in not_found_markers)
        ):
            raise APIError(
                code="OBJECT_NOT_FOUND",
                message="Objeto não encontrado.",
                status_code=404,
            ) from exc

        if any(marker in message_lower for marker in namespace_markers):
            raise APIError(
                code="OBJECT_NAMESPACE_ERROR",
                message=message,
                status_code=403,
            ) from exc

        raise APIError(
            code="OBJECT_DOWNLOAD_FAILED",
            message=message,
            status_code=409,
        ) from exc

        raise APIError(
            code=code,
            message=message,
            status_code=status_code,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="OBJECT_DOWNLOAD_ERROR",
            message="Falha interna no download",
            status_code=500,
        ) from exc
