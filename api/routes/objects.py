from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from api.auth import AuthenticatedPrincipal
from api.config import MAX_IDEMPOTENCY_KEY_BYTES
from api.dependencies import (
    require_namespace_permission,
    require_permission,
)
from api.errors import APIError
from api.schemas.object import (
    ObjectCreateRequest,
    ObjectCreateResponse,
    ObjectMetadataResponse,
    ObjectVerifyResponse,
    ObjectDeleteResponse,
    ObjectListResponse,
)
from api.services import object_service
from node.object_manager import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    IdempotencyReplayError,
)


router = APIRouter(
    prefix="/api/v1/namespaces/{namespace}/objects",
    tags=["objects"],
)


@router.post(
    "",
    response_model=ObjectCreateResponse,
    status_code=201,
)
async def create_object(
    namespace: str,
    payload: ObjectCreateRequest,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.create")
    ),
):
    try:
        if idempotency_key is not None:
            key_bytes = idempotency_key.encode("utf-8")

            if len(key_bytes) > MAX_IDEMPOTENCY_KEY_BYTES:
                raise APIError(
                    code="IDEMPOTENCY_KEY_TOO_LARGE",
                    message="Idempotency-Key excede o limite permitido.",
                    status_code=413,
                    details={
                        "max_bytes": MAX_IDEMPOTENCY_KEY_BYTES,
                        "received_bytes": len(key_bytes),
                    },
                )

        return object_service.create_object(
            namespace=namespace,
            data=payload.data,
            idempotency_key=idempotency_key,
        )

    except APIError:
        raise

    except IdempotencyConflictError as exc:
        raise APIError(
            code="IDEMPOTENCY_KEY_CONFLICT",
            message=str(exc),
            status_code=409,
        ) from exc

    except IdempotencyInProgressError as exc:
        raise APIError(
            code="IDEMPOTENCY_IN_PROGRESS",
            message=str(exc),
            status_code=409,
        ) from exc

    except IdempotencyReplayError as exc:
        raise APIError(
            code="IDEMPOTENCY_REPLAY_ERROR",
            message=str(exc),
            status_code=409,
        ) from exc

    except object_service.ObjectServiceError as exc:
        message = str(exc)

        if "excede o limite máximo permitido" in message.lower():
            raise APIError(
                code="OBJECT_TOO_LARGE",
                message=message,
                status_code=413,
                details={
                    "max_bytes": __import__(
                        "api.config",
                        fromlist=["MAX_OBJECT_SIZE_BYTES"],
                    ).MAX_OBJECT_SIZE_BYTES,
                },
            ) from exc

        if "namespace" in message.lower():
            raise APIError(
                code="OBJECT_NAMESPACE_ERROR",
                message=message,
                status_code=400,
            ) from exc

        raise APIError(
            code="OBJECT_CREATE_FAILED",
            message=message,
            status_code=400,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="OBJECT_CREATE_ERROR",
            message="Falha interna ao criar objeto",
            status_code=500,
        ) from exc


@router.get(
    "",
    response_model=ObjectListResponse,
)
async def list_objects(
    namespace: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.read")
    ),
):
    try:
        items = object_service.list_namespace_objects(
            namespace=namespace,
        )

        return {
            "namespace": namespace,
            "objects": items,
            "count": len(items),
        }

    except Exception as exc:
        raise APIError(
            code="OBJECT_LIST_ERROR",
            message="Falha ao listar objetos",
            status_code=500,
        ) from exc


@router.get(
    "/{object_id}",
    response_model=ObjectMetadataResponse,
)
async def get_object(
    namespace: str,
    object_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.read")
    ),
):
    try:
        return object_service.get_object(
            namespace=namespace,
            object_id=object_id,
        )

    except object_service.ObjectServiceError as exc:
        raise APIError(
            code="OBJECT_NOT_FOUND",
            message=str(exc),
            status_code=404,
        ) from exc


@router.get(
    "/{object_id}/verify",
    response_model=ObjectVerifyResponse,
)
async def verify_object(
    namespace: str,
    object_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.read")
    ),
):
    try:
        return object_service.verify_object_service(
            namespace=namespace,
            object_id=object_id,
        )

    except object_service.ObjectServiceError as exc:
        raise APIError(
            code="OBJECT_NOT_FOUND",
            message=str(exc),
            status_code=404,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="OBJECT_VERIFY_ERROR",
            message="Falha ao verificar objeto",
            status_code=500,
        ) from exc


@router.delete(
    "/{object_id}",
    response_model=ObjectDeleteResponse,
)
async def delete_object(
    namespace: str,
    object_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.delete")
    ),
):
    try:
        result = object_service.delete_object(
            namespace=namespace,
            object_id=object_id,
        )

        if not result["deleted"]:
            raise APIError(
                code="OBJECT_DELETE_FAILED",
                message=result["status"],
                status_code=409,
            )

        return result

    except object_service.ObjectServiceError as exc:
        raise APIError(
            code="OBJECT_NOT_FOUND",
            message=str(exc),
            status_code=404,
        ) from exc

    except APIError:
        raise

    except Exception as exc:
        raise APIError(
            code="OBJECT_DELETE_ERROR",
            message="Falha interna ao excluir objeto",
            status_code=500,
        ) from exc
