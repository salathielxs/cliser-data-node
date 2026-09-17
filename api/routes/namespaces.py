from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.auth import AuthenticatedPrincipal
from api.dependencies import (
    require_namespace_permission,
    require_namespace_management_permission,
    require_permission,
)
from api.errors import APIError
from api.schemas.namespace import (
    NamespaceCreateRequest,
    NamespaceListResponse,
    NamespaceResponse,
)
from api.services import namespace_service

router = APIRouter(
    prefix="/api/v1/namespaces",
    tags=["namespaces"],
)


@router.post(
    "",
    response_model=NamespaceResponse,
    status_code=201,
)
async def create_namespace(
    payload: NamespaceCreateRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission("namespace.manage")
    ),
):
    try:
        return namespace_service.create_namespace(
            namespace=payload.namespace,
            quota_bytes=payload.quota_bytes,
        )

    except ValueError as exc:
        raise APIError(
            code="NAMESPACE_INVALID",
            message=str(exc),
            status_code=400,
        ) from exc

    except TypeError as exc:
        raise APIError(
            code="NAMESPACE_INVALID",
            message=str(exc),
            status_code=400,
        ) from exc


@router.get(
    "",
    response_model=NamespaceListResponse,
)
async def list_namespaces(
    status: str | None = Query(
        default=None,
        pattern="^(ACTIVE|DISABLED)$",
    ),
    principal: AuthenticatedPrincipal = Depends(
        require_permission("namespace.read")
    ),
):
    try:
        items = namespace_service.list_namespaces(
            status=status,
        )

        return {
            "items": items,
            "total": len(items),
        }

    except ValueError as exc:
        raise APIError(
            code="NAMESPACE_INVALID",
            message=str(exc),
            status_code=400,
        ) from exc


@router.get(
    "/{namespace}",
    response_model=NamespaceResponse,
)
async def get_namespace(
    namespace: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("namespace.read")
    ),
):
    result = namespace_service.get_namespace(namespace)

    if result is None:
        raise APIError(
            code="NAMESPACE_NOT_FOUND",
            message=f"Namespace não encontrado: {namespace}",
            status_code=404,
        )

    return result


@router.post(
    "/{namespace}/enable",
    response_model=NamespaceResponse,
)
async def enable_namespace(
    namespace: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_management_permission()
    ),
):
    try:
        return namespace_service.enable_namespace(namespace)

    except KeyError as exc:
        raise APIError(
            code="NAMESPACE_NOT_FOUND",
            message=str(exc),
            status_code=404,
        ) from exc

    except ValueError as exc:
        raise APIError(
            code="NAMESPACE_INVALID",
            message=str(exc),
            status_code=400,
        ) from exc


@router.post(
    "/{namespace}/disable",
    response_model=NamespaceResponse,
)
async def disable_namespace(
    namespace: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_management_permission()
    ),
):
    try:
        return namespace_service.disable_namespace(namespace)

    except KeyError as exc:
        raise APIError(
            code="NAMESPACE_NOT_FOUND",
            message=str(exc),
            status_code=404,
        ) from exc

    except ValueError as exc:
        raise APIError(
            code="NAMESPACE_INVALID",
            message=str(exc),
            status_code=400,
        ) from exc
