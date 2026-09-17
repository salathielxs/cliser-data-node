from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from node.health import run_health


router = APIRouter(
    prefix="/api/v1/health",
    tags=["health"],
)


@router.get("")
def health():
    result = run_health()

    return {
        "service": "cliser-data-node",
        "status": result["status"],
        "checks": result["checks"],
    }


@router.get("/live")
def health_live():
    return {
        "status": "ok",
        "service": "cliser-data-node",
        "api_version": "v1",
    }


@router.get("/ready")
def health_ready():
    result = run_health()

    if result["status"] == "CRITICAL":
        return JSONResponse(
            status_code=503,
            content={
                "service": "cliser-data-node",
                "status": "NOT_READY",
                "checks": result["checks"],
            },
        )

    return {
        "service": "cliser-data-node",
        "status": "READY",
        "checks": result["checks"],
    }
