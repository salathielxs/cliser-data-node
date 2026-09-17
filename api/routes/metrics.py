from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_permission
from api.errors import APIError
from api.schemas.metrics import MetricsResponse
from api.services import metrics_service


router = APIRouter(
    prefix="/api/v1/metrics",
    tags=["metrics"],
)


@router.get(
    "",
    response_model=MetricsResponse,
)
async def get_metrics(
    principal: AuthenticatedPrincipal = Depends(
        require_permission("node.manage")
    ),
):
    try:
        return metrics_service.get_metrics()

    except metrics_service.MetricsServiceError as exc:
        raise APIError(
            code="METRICS_GET_ERROR",
            message="Falha ao consultar métricas",
            status_code=500,
            details={
                "reason": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise APIError(
            code="METRICS_GET_ERROR",
            message="Falha interna ao consultar métricas",
            status_code=500,
        ) from exc
