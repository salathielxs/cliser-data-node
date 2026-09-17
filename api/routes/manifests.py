from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_namespace_permission
from api.errors import APIError
from api.schemas.manifest import ManifestResponse
from api.services import manifest_service


router = APIRouter(
    prefix="/api/v1/namespaces/{namespace}/objects",
    tags=["manifests"],
)


@router.get(
    "/{object_id}/manifest",
    response_model=ManifestResponse,
)
async def get_manifest(
    namespace: str,
    object_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.read")
    ),
):
    try:
        return manifest_service.get_object_manifest(
            namespace=namespace,
            object_id=object_id,
        )

    except manifest_service.ManifestServiceError as exc:
        message = str(exc)

        if "não encontrado" in message.lower():
            raise APIError(
                code="MANIFEST_NOT_FOUND",
                message=message,
                status_code=404,
            ) from exc

        if "fora do namespace" in message.lower():
            raise APIError(
                code="MANIFEST_NAMESPACE_ERROR",
                message=message,
                status_code=403,
            ) from exc

        raise APIError(
            code="MANIFEST_UNAVAILABLE",
            message=message,
            status_code=409,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="MANIFEST_ERROR",
            message="Falha interna ao obter manifest",
            status_code=500,
        ) from exc
