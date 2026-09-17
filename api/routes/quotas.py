from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_namespace_permission
from api.errors import APIError
from api.schemas.quota import (
    QuotaResponse,
    QuotaUpdateRequest,
)
from api.services import quota_service


router = APIRouter(
    prefix="/api/v1/namespaces/{namespace}/quota",
    tags=["quotas"],
)


@router.get(
    "",
    response_model=QuotaResponse,
)
async def get_quota(
    namespace: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("namespace.read")
    ),
):
    try:
        return quota_service.get_quota(
            namespace=namespace,
        )

    except quota_service.QuotaServiceError as exc:
        if str(exc) == "Quota não configurada":
            raise APIError(
                code="QUOTA_NOT_FOUND",
                message=str(exc),
                status_code=404,
            ) from exc

        raise APIError(
            code="QUOTA_GET_ERROR",
            message=str(exc),
            status_code=400,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="QUOTA_GET_ERROR",
            message="Falha interna ao consultar quota",
            status_code=500,
        ) from exc


@router.put(
    "",
    response_model=QuotaResponse,
)
async def update_quota(
    namespace: str,
    request: QuotaUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("quota.manage")
    ),
):
    try:
        return quota_service.set_quota(
            namespace=namespace,
            quota_bytes=request.quota_bytes,
            mode=request.mode,
        )

    except quota_service.QuotaServiceError as exc:
        raise APIError(
            code="QUOTA_UPDATE_ERROR",
            message=str(exc),
            status_code=400,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="QUOTA_UPDATE_ERROR",
            message="Falha interna ao definir quota",
            status_code=500,
        ) from exc
