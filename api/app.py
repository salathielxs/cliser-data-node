from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from api.middleware import (
    RequestIDMiddleware,
    RequestSizeLimitMiddleware,
)
from api.rate_limit_middleware import RateLimitMiddleware
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from api.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from api.routes.auth import router as auth_router
from api.routes.namespaces import router as namespaces_router
from api.routes.objects import router as objects_router
from api.routes.upload import router as upload_router
from api.routes.download import router as download_router
from api.routes.metadata import router as metadata_router
from api.routes.manifests import router as manifests_router
from api.routes.transactions import router as transactions_router
from api.routes.quotas import router as quotas_router
from api.routes.health import router as health_router
from api.routes.metrics import router as metrics_router
from api.routes.lifecycle import router as lifecycle_router

APP_NAME = "CLISER DATA NODE API"
API_VERSION = "v1"

app = FastAPI(
    title=APP_NAME,
    version="1.0.0",
    description="HTTP API do CLISER DATA NODE",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)

# ---------------------------------------------------------------------------
# OpenAPI runtime security
# ---------------------------------------------------------------------------

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=APP_NAME,
        version="1.0.0",
        description="HTTP API do CLISER DATA NODE",
        routes=app.routes,
    )

    schema.setdefault("components", {})
    schema["components"].setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["bearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "token",
    }

    public_paths = {
        "/api/v1/health",
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/openapi.json",
        "/api/v1/docs",
        "/api/v1/redoc",
    }

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue

            if path in public_paths:
                operation["security"] = []
            else:
                operation["security"] = [
                    {"bearerAuth": []}
                ]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi



app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)
app.add_exception_handler(Exception, unhandled_exception_handler)


app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(lifecycle_router)
app.include_router(auth_router)
app.include_router(namespaces_router)
app.include_router(objects_router)
app.include_router(upload_router)
app.include_router(download_router)
app.include_router(metadata_router)
app.include_router(manifests_router)
app.include_router(transactions_router)
app.include_router(quotas_router)
