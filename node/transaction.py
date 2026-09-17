from datetime import datetime, timezone
from enum import Enum

from node.registry import (
    get_transaction,
    get_transaction_journal,
    list_transactions,
    update_transaction_state,
)


class TransactionState(str, Enum):
    PREPARED = "PREPARED"
    WRITING = "WRITING"
    VERIFYING = "VERIFYING"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    ROLLBACK = "ROLLBACK"


VALID_TRANSITIONS = {
    TransactionState.PREPARED: {
        TransactionState.WRITING,
        TransactionState.FAILED,
    },
    TransactionState.WRITING: {
        TransactionState.VERIFYING,
        TransactionState.FAILED,
    },
    TransactionState.VERIFYING: {
        TransactionState.COMMITTING,
        TransactionState.FAILED,
    },
    TransactionState.COMMITTING: {
        TransactionState.COMMITTED,
        TransactionState.FAILED,
    },
    TransactionState.FAILED: {
        TransactionState.ROLLBACK,
    },
    TransactionState.ROLLBACK: set(),
    TransactionState.COMMITTED: set(),
}


RECOVERABLE_STATES = {
    TransactionState.PREPARED.value,
    TransactionState.WRITING.value,
    TransactionState.VERIFYING.value,
    TransactionState.COMMITTING.value,
}


TERMINAL_STATES = {
    TransactionState.COMMITTED.value,
    TransactionState.ROLLBACK.value,
}


class Transaction:
    def __init__(self, transaction_id):
        if not transaction_id:
            raise ValueError("transaction_id inválido.")

        self.transaction_id = transaction_id
        self.state = TransactionState.PREPARED
        self.created_at = self._now()
        self.updated_at = self.created_at
        self.error = None

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def transition(self, new_state):
        if not isinstance(new_state, TransactionState):
            new_state = TransactionState(new_state)

        allowed = VALID_TRANSITIONS[self.state]

        if new_state not in allowed:
            raise ValueError(
                f"Transição inválida: "
                f"{self.state.value} -> {new_state.value}"
            )

        self.state = new_state
        self.updated_at = self._now()

        return self.state

    def fail(self, error):
        self.error = str(error)

        if self.state != TransactionState.FAILED:
            self.transition(TransactionState.FAILED)

        return self.state

    def rollback(self):
        if self.state != TransactionState.FAILED:
            raise ValueError(
                "Rollback somente após FAILED."
            )

        return self.transition(TransactionState.ROLLBACK)

    def commit(self):
        if self.state != TransactionState.COMMITTING:
            raise ValueError(
                "Commit somente a partir de COMMITTING."
            )

        return self.transition(TransactionState.COMMITTED)

    def snapshot(self):
        return {
            "transaction_id": self.transaction_id,
            "state": self.state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }


def _normalize_transaction_state(state):
    try:
        return TransactionState(state)
    except (ValueError, TypeError):
        return None




