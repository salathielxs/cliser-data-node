#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class RecoveryState(str, Enum):
    NEW = "NEW"
    PREPARED = "PREPARED"
    WRITING = "WRITING"
    VERIFYING = "VERIFYING"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    RECOVERABLE = "RECOVERABLE"
    IN_DOUBT = "IN_DOUBT"
    CORRUPTED = "CORRUPTED"
    QUARANTINED = "QUARANTINED"


class RecoveryAction(str, Enum):
    RECOVER = "RECOVER"
    REVERIFY = "REVERIFY"
    FINALIZE = "FINALIZE"
    ROLLBACK = "ROLLBACK"
    QUARANTINE = "QUARANTINE"
    COMPLETE = "COMPLETE"


@dataclass
class Transaction:
    transaction_id: str
    idempotency_key: str
    state: str
    payload_hash: str
    result_hash: str | None = None

    write_started: bool = False
    write_completed: bool = False

    verification_started: bool = False
    verification_completed: bool = False
    verification_passed: bool = False

    commit_started: bool = False
    commit_completed: bool = False

    rollback_started: bool = False
    rollback_completed: bool = False

    error_code: str | None = None


def hash_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    return hashlib.sha256(raw).hexdigest()


class TransactionJournal:

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, transaction: Transaction) -> None:
        data = asdict(transaction)

        fd, temp_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".transaction.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    data,
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(temp_path, self.path)

        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def load(self) -> Transaction | None:
        if not self.path.exists():
            return None

        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        return Transaction(**data)


class RecoveryEngine:

    def __init__(
        self,
        journal: TransactionJournal,
        persisted_state: dict | None = None,
    ):
        self.journal = journal
        self.persisted_state = persisted_state or {}

    def inspect(self, transaction: Transaction) -> dict:

        return {
            "transaction_id": transaction.transaction_id,
            "state": transaction.state,
            "write_completed": transaction.write_completed,
            "verification_completed": transaction.verification_completed,
            "verification_passed": transaction.verification_passed,
            "commit_completed": transaction.commit_completed,
            "rollback_completed": transaction.rollback_completed,
            "persisted": self.persisted_state.get(
                transaction.transaction_id,
                False,
            ),
        }

    def decide(self, transaction: Transaction) -> RecoveryAction:

        # Already fully committed.
        if (
            transaction.state == RecoveryState.COMMITTED
            and transaction.commit_completed
        ):
            return RecoveryAction.COMPLETE

        # Commit may have persisted before crash.
        if (
            transaction.commit_started
            and self.persisted_state.get(
                transaction.transaction_id,
                False,
            )
        ):
            return RecoveryAction.FINALIZE

        # Invalid or failed verification.
        if (
            transaction.error_code
            or (
                transaction.verification_completed
                and not transaction.verification_passed
            )
        ):
            return RecoveryAction.ROLLBACK

        # Verification started but did not finish.
        if (
            transaction.state == RecoveryState.VERIFYING
            and not transaction.verification_completed
        ):
            return RecoveryAction.REVERIFY

        # Write started but did not finish.
        if (
            transaction.state == RecoveryState.WRITING
            and not transaction.write_completed
        ):
            return RecoveryAction.ROLLBACK

        # Prepared transaction with no write.
        if transaction.state == RecoveryState.PREPARED:
            return RecoveryAction.ROLLBACK

        # Writing completed but verification has not.
        if (
            transaction.write_completed
            and not transaction.verification_completed
        ):
            return RecoveryAction.REVERIFY

        # Commit started but is not known to have completed.
        if (
            transaction.state == RecoveryState.COMMITTING
            and not transaction.commit_completed
        ):
            return RecoveryAction.RECOVER

        return RecoveryAction.QUARANTINE

    def execute(
        self,
        transaction: Transaction,
        action: RecoveryAction,
    ) -> Transaction:

        if action == RecoveryAction.COMPLETE:
            transaction.state = RecoveryState.COMMITTED
            return transaction

        if action == RecoveryAction.FINALIZE:
            transaction.commit_completed = True
            transaction.state = RecoveryState.COMMITTED
            return transaction

        if action == RecoveryAction.REVERIFY:
            transaction.verification_started = True
            transaction.verification_completed = True
            transaction.verification_passed = True
            transaction.state = RecoveryState.COMMITTING
            return transaction

        if action == RecoveryAction.RECOVER:
            transaction.commit_started = True

            if self.persisted_state.get(
                transaction.transaction_id,
                False,
            ):
                transaction.commit_completed = True
                transaction.state = RecoveryState.COMMITTED
            else:
                transaction.verification_started = True
                transaction.verification_completed = True
                transaction.verification_passed = True
                transaction.commit_completed = True
                transaction.state = RecoveryState.COMMITTED

            return transaction

        if action == RecoveryAction.ROLLBACK:
            transaction.rollback_started = True
            transaction.rollback_completed = True
            transaction.state = RecoveryState.ROLLED_BACK
            return transaction

        if action == RecoveryAction.QUARANTINE:
            transaction.state = RecoveryState.QUARANTINED
            return transaction

        transaction.state = RecoveryState.IN_DOUBT
        return transaction

    def recover(self) -> tuple[Transaction | None, RecoveryAction | None]:

        transaction = self.journal.load()

        if transaction is None:
            return None, None

        action = self.decide(transaction)

        transaction = self.execute(
            transaction,
            action,
        )

        self.journal.save(transaction)

        return transaction, action


def make_transaction(
    transaction_id: str,
    state: RecoveryState,
    payload: object,
) -> Transaction:

    return Transaction(
        transaction_id=transaction_id,
        idempotency_key=f"idem_{transaction_id}",
        state=state.value,
        payload_hash=hash_payload(payload),
    )


if __name__ == "__main__":

    print("CLISER DATA NODE")
    print("Transaction Recovery Engine")
    print("15.2.6-F")
