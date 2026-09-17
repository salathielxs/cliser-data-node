from __future__ import annotations

from typing import Any

from node.registry import (
    get_transaction as registry_get_transaction,
    list_transactions as registry_list_transactions,
)


class TransactionServiceError(Exception):
    pass


def _serialize_transaction(
    transaction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "transaction_id": transaction["transaction_id"],
        "object_id": transaction["object_id"],
        "namespace": transaction["namespace"],
        "operation": transaction["operation"],
        "state": transaction["state"],
        "created_at": transaction["created_at"],
        "updated_at": transaction["updated_at"],
    }


def get_transaction(
    transaction_id: str,
) -> dict[str, Any]:
    transaction = registry_get_transaction(
        transaction_id
    )

    if transaction is None:
        raise TransactionServiceError(
            "Transação não encontrada"
        )

    return _serialize_transaction(transaction)


def list_transactions() -> list[dict[str, Any]]:
    rows = registry_list_transactions()

    result: list[dict[str, Any]] = []

    for row in rows:
        # Registry retorna:
        # (
        #   transaction_id,
        #   object_id,
        #   namespace,
        #   operation,
        #   state,
        #   created_at,
        #   updated_at,
        #   error
        # )

        (
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at,
            error,
        ) = row

        result.append(
            {
                "transaction_id": transaction_id,
                "object_id": object_id,
                "namespace": namespace,
                "operation": operation,
                "state": state,
                "created_at": created_at,
                "updated_at": updated_at,
            }
        )

    return result
