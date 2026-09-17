from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from api.auth import AuthenticatedPrincipal
from api.config import (
    MAX_FILENAME_BYTES,
    MAX_OBJECT_SIZE_BYTES,
    MAX_UPLOAD_SIZE_BYTES,
)
from api.dependencies import require_namespace_permission
from api.errors import APIError
from api.schemas.upload import UploadResponse
from api.services import upload_service


router = APIRouter(
    prefix="/api/v1/namespaces/{namespace}/uploads",
    tags=["uploads"],
)


@router.post(
    "",
    response_model=UploadResponse,
    status_code=201,
)
async def upload_object(
    namespace: str,
    file: UploadFile = File(...),
    principal: AuthenticatedPrincipal = Depends(
        require_namespace_permission("object.create")
    ),
):
    try:
        filename = file.filename or "unnamed"

        filename_bytes = filename.encode("utf-8")

        if len(filename_bytes) > MAX_FILENAME_BYTES:
            raise APIError(
                code="FILENAME_TOO_LARGE",
                message="Filename excede o limite permitido.",
                status_code=413,
                details={
                    "max_bytes": MAX_FILENAME_BYTES,
                    "received_bytes": len(filename_bytes),
                },
            )

        chunks = []
        total = 0
        chunk_size = 1024 * 1024

        while True:
            chunk = await file.read(chunk_size)

            if not chunk:
                break

            total += len(chunk)

            if total > MAX_OBJECT_SIZE_BYTES:
                raise APIError(
                    code="OBJECT_TOO_LARGE",
                    message="Objeto excede o limite máximo permitido.",
                    status_code=413,
                    details={
                        "max_bytes": MAX_OBJECT_SIZE_BYTES,
                        "received_bytes": total,
                    },
                )

            if total > MAX_UPLOAD_SIZE_BYTES:
                raise APIError(
                    code="UPLOAD_TOO_LARGE",
                    message="Upload excede o limite permitido.",
                    status_code=413,
                    details={
                        "max_bytes": MAX_UPLOAD_SIZE_BYTES,
                        "received_bytes": total,
                    },
                )

            chunks.append(chunk)

        data = b"".join(chunks)

        return upload_service.upload_object(
            namespace=namespace,
            filename=filename,
            data=data,
        )

    except APIError:
        raise

    except upload_service.UploadServiceError as exc:
        raise APIError(
            code="UPLOAD_FAILED",
            message=str(exc),
            status_code=400,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="UPLOAD_ERROR",
            message="Falha interna no upload",
            status_code=500,
        ) from exc
