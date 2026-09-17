from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

        super().__init__(message)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    request_id = _request_id(request)

    error: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }

    if details:
        error["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={"error": error},
        headers={
            "X-Request-ID": request_id or "",
        },
    )


async def api_error_handler(
    request: Request,
    exc: APIError,
) -> JSONResponse:
    return _response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    detail = exc.detail

    code = "HTTP_ERROR"
    message = "HTTP request failed."
    details: dict | None = None

    if isinstance(detail, dict):
        code = str(detail.get("code", code))
        message = str(detail.get("message", message))

        extra = {
            key: value
            for key, value in detail.items()
            if key not in {"code", "message"}
        }

        if extra:
            details = extra
    elif isinstance(detail, str):
        message = detail
    elif detail is not None:
        details = {"detail": detail}

    return _response(
        request=request,
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()

    normalized_errors = []

    for error in errors:
        normalized_errors.append(
            {
                "type": error.get("type"),
                "loc": list(error.get("loc", [])),
                "msg": error.get("msg"),
            }
        )

    return _response(
        request=request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        details={
            "errors": normalized_errors,
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return _response(
        request=request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="Internal server error.",
    )
