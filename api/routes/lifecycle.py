from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_permission
from api.errors import APIError
from api.services import lifecycle_service


router = APIRouter(
    prefix="/api/v1/lifecycle",
    tags=["lifecycle"],
)


@router.post("/gc")
async def garbage_collect(
    principal: AuthenticatedPrincipal = Depends(
        require_permission("node.manage")
    ),
):
    try:
        return lifecycle_service.garbage_collect()

    except lifecycle_service.LifecycleServiceError as exc:
        raise APIError(
            code="LIFECYCLE_GC_ERROR",
            message="Falha ao executar garbage collection",
            status_code=500,
            details={
                "reason": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise APIError(
            code="LIFECYCLE_GC_ERROR",
            message="Falha interna ao executar garbage collection",
            status_code=500,
        ) from exc


@router.post("/rebuild-refcounts")
async def rebuild_refcounts(
    principal: AuthenticatedPrincipal = Depends(
        require_permission("node.manage")
    ),
):
    try:
        return lifecycle_service.rebuild_refcounts()

    except lifecycle_service.LifecycleServiceError as exc:
        raise APIError(
            code="LIFECYCLE_REFCOUNT_ERROR",
            message="Falha ao reconstruir contadores de referência",
            status_code=500,
            details={
                "reason": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise APIError(
            code="LIFECYCLE_REFCOUNT_ERROR",
            message="Falha interna ao reconstruir contadores de referência",
            status_code=500,
        ) from exc


@router.post("/integrity-check")
async def integrity_check(
    principal: AuthenticatedPrincipal = Depends(
        require_permission("node.manage")
    ),
):
    try:
        return lifecycle_service.integrity_check()

    except lifecycle_service.LifecycleServiceError as exc:
        raise APIError(
            code="LIFECYCLE_INTEGRITY_ERROR",
            message="Falha ao executar verificação de integridade",
            status_code=500,
            details={
                "reason": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise APIError(
            code="LIFECYCLE_INTEGRITY_ERROR",
            message="Falha interna ao executar verificação de integridade",
            status_code=500,
        ) from exc
