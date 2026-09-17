from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_namespace_permission
from api.errors import APIError
from api.schemas.object import ObjectMetadataResponse
from api.services import metadata_service


router = APIRouter(
    prefix="/api/v1/namespaces/{namespace}/objects",
    tags=["metadata"],
)


@router.get("/{object_id}/metadata", response_model=ObjectMetadataResponse)
async def get_object_metadata(
    namespace: str,
    object_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.read")
    ),
):
    try:
        return metadata_service.get_object_metadata(
            namespace=namespace,
            object_id=object_id,
        )

    except metadata_service.MetadataServiceError as exc:
        message = str(exc)

        if "não encontrado" in message.lower():
            raise APIError(
                code="OBJECT_NOT_FOUND",
                message=message,
                status_code=404,
            ) from exc

        if "fora do namespace" in message.lower():
            raise APIError(
                code="OBJECT_NAMESPACE_ERROR",
                message=message,
                status_code=403,
            ) from exc

        raise APIError(
            code="OBJECT_METADATA_FAILED",
            message=message,
            status_code=409,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="OBJECT_METADATA_ERROR",
            message="Falha interna ao obter metadata",
            status_code=500,
        ) from exc
