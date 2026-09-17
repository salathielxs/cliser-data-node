from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.auth import get_optional_principal

from api.rate_limit import rate_limiter
from api.rate_limit_policy import get_rate_limit_policy


class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        policy = get_rate_limit_policy(
            request.method
        )

        principal = get_optional_principal(
            request.headers.get("Authorization")
        )

        if principal is not None:
            key = (
                f"authenticated:"
                f"{principal.identity_id}"
                f"|credential:"
                f"{principal.credential_id or 'none'}"
            )
        else:
            client = request.client

            if client is not None:
                client_key = client.host
            else:
                client_key = "unknown"

            key = f"anonymous:{client_key}"

        result = rate_limiter.check(
            key=key,
            limit=policy.limit,
            window_seconds=policy.window_seconds,
        )

        if not result.allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": (
                            "Limite de requisições excedido."
                        ),
                        "details": {
                            "operation": policy.operation,
                            "limit": result.limit,
                            "remaining": result.remaining,
                            "retry_after": result.retry_after,
                        },
                    }
                },
            )

            response.headers[
                "Retry-After"
            ] = str(result.retry_after)

            response.headers[
                "X-RateLimit-Limit"
            ] = str(result.limit)

            response.headers[
                "X-RateLimit-Remaining"
            ] = str(result.remaining)

            return response

        response = await call_next(request)

        response.headers[
            "X-RateLimit-Limit"
        ] = str(result.limit)

        response.headers[
            "X-RateLimit-Remaining"
        ] = str(result.remaining)

        return response
