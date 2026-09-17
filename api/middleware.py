from __future__ import annotations

import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.logging import logger


REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER)

        if not request_id:
            request_id = str(uuid4())

        request.state.request_id = request_id

        started_at = time.perf_counter()

        response = await call_next(request)

        duration_ms = round(
            (time.perf_counter() - started_at) * 1000,
            3,
        )

        response.headers[REQUEST_ID_HEADER] = request_id

        error_code = getattr(request.state, "error_code", None)

        extra = {
            "event": (
                "http_error"
                if response.status_code >= 400
                else "http_request"
            ),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }

        if error_code is not None:
            extra["error_code"] = error_code

        try:
            from api.auth import get_optional_principal

            principal = get_optional_principal(
                request.headers.get("Authorization")
            )

            if principal is not None:
                extra["identity_id"] = principal.identity_id
                extra["credential_id"] = principal.credential_id
                extra["namespace"] = principal.namespace

        except Exception:
            # Logging nunca deve derrubar uma requisição.
            pass

        logger.info(
            "HTTP request completed",
            extra=extra,
        )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        from api.config import (
            MAX_REQUEST_BODY_BYTES,
            MAX_QUERY_STRING_BYTES,
        )

        query_string = request.scope.get(
            "query_string",
            b"",
        )

        if len(query_string) > MAX_QUERY_STRING_BYTES:
            request.state.error_code = "QUERY_STRING_TOO_LARGE"

            return JSONResponse(
                status_code=414,
                content={
                    "error": {
                        "code": "QUERY_STRING_TOO_LARGE",
                        "message": (
                            "Query string excede "
                            "o limite permitido."
                        ),
                        "details": {
                            "max_bytes": MAX_QUERY_STRING_BYTES,
                            "received_bytes": len(query_string),
                        },
                    }
                },
            )

        is_upload = (
            request.method in {"POST", "PUT", "PATCH"}
            and request.url.path.endswith("/uploads")
        )

        content_length = request.headers.get(
            "content-length"
        )

        if content_length is not None:

            try:
                content_length_value = int(
                    content_length
                )

            except (TypeError, ValueError):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "INVALID_CONTENT_LENGTH",
                            "message": "Content-Length inválido.",
                        }
                    },
                )

            if content_length_value < 0:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": {
                            "code": "INVALID_CONTENT_LENGTH",
                            "message": "Content-Length inválido.",
                        }
                    },
                )

            if (
                not is_upload
                and content_length_value > MAX_REQUEST_BODY_BYTES
            ):
                request.state.error_code = "REQUEST_BODY_TOO_LARGE"

                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "REQUEST_BODY_TOO_LARGE",
                            "message": (
                                "Corpo da requisição excede "
                                "o limite permitido."
                            ),
                            "details": {
                                "max_bytes": MAX_REQUEST_BODY_BYTES,
                                "received_bytes": content_length_value,
                            },
                        }
                    },
                )

        return await call_next(request)
