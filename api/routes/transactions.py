from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import AuthenticatedPrincipal
from api.dependencies import require_permission
from api.errors import APIError
from api.schemas.transaction import (
    TransactionListResponse,
    TransactionResponse,
)
from api.services import transaction_service


router = APIRouter(
    prefix="/api/v1/transactions",
    tags=["transactions"],
)


@router.get(
    "",
    response_model=TransactionListResponse,
)
async def list_transactions(
    principal: AuthenticatedPrincipal = Depends(
        require_permission("node.manage")
    ),
):
    try:
        items = transaction_service.list_transactions()

        return {
            "transactions": items,
            "count": len(items),
        }

    except Exception as exc:
        raise APIError(
            code="TRANSACTION_LIST_ERROR",
            message="Falha ao listar transações",
            status_code=500,
        ) from exc


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
)
async def get_transaction(
    transaction_id: str,
    principal: AuthenticatedPrincipal = Depends(
        require_permission("node.manage")
    ),
):
    try:
        return transaction_service.get_transaction(
            transaction_id=transaction_id,
        )

    except transaction_service.TransactionServiceError as exc:
        raise APIError(
            code="TRANSACTION_NOT_FOUND",
            message=str(exc),
            status_code=404,
        ) from exc

    except Exception as exc:
        raise APIError(
            code="TRANSACTION_GET_ERROR",
            message="Falha interna ao consultar transação",
            status_code=500,
        ) from exc
