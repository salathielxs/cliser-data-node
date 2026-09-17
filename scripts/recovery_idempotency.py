#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import tempfile

from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class State(str, Enum):
    NEW = "NEW"
    PREPARED = "PREPARED"
    WRITING = "WRITING"
    VERIFYING = "VERIFYING"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    QUARANTINED = "QUARANTINED"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    ROLLBACK = "ROLLBACK"
    REVERIFY = "REVERIFY"
    RECOVER = "RECOVER"
    FINALIZE = "FINALIZE"
    COMPLETE = "COMPLETE"
    QUARANTINE = "QUARANTINE"


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
    persisted: bool = False

    recovery_count: int = 0
    commit_count: int = 0

    error_code: str | None = None


class Journal:

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, tx: Transaction):
        fd, tmp = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".journal.",
            suffix=".tmp",
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as handle:

                json.dump(
                    asdict(tx),
                    handle,
                    indent=2,
                    sort_keys=True,
                )

                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp, self.path)

        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self) -> Transaction:
        with self.path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            data = json.load(handle)

        return Transaction(**data)


class RecoveryEngine:

    def __init__(self, journal: Journal):
        self.journal = journal

    def decide(self, tx: Transaction) -> RecoveryAction:

        if (
            tx.state == State.COMMITTED.value
            and tx.commit_completed
        ):
            return RecoveryAction.COMPLETE

        if (
            tx.commit_started
            and tx.persisted
            and not tx.commit_completed
        ):
            return RecoveryAction.FINALIZE

        if tx.state == State.PREPARED.value:
            return RecoveryAction.ROLLBACK

        if (
            tx.state == State.WRITING.value
            and not tx.write_completed
        ):
            return RecoveryAction.ROLLBACK

        if (
            tx.state == State.WRITING.value
            and tx.write_completed
            and not tx.verification_completed
        ):
            return RecoveryAction.REVERIFY

        if (
            tx.state == State.VERIFYING.value
            and not tx.verification_completed
        ):
            return RecoveryAction.REVERIFY

        if (
            tx.state == State.COMMITTING.value
            and not tx.persisted
        ):
            return RecoveryAction.RECOVER

        if (
            tx.write_completed
            and tx.verification_completed
            and tx.verification_passed
        ):
            return RecoveryAction.RECOVER

        return RecoveryAction.QUARANTINE

    def execute(
        self,
        tx: Transaction,
        action: RecoveryAction,
    ) -> Transaction:

        tx.recovery_count += 1

        if action == RecoveryAction.COMPLETE:
            tx.state = State.COMMITTED.value
            return tx

        if action == RecoveryAction.FINALIZE:

            if not tx.commit_completed:
                tx.commit_completed = True

                if tx.commit_count == 0:
                    tx.commit_count = 1

            tx.state = State.COMMITTED.value
            return tx

        if action == RecoveryAction.ROLLBACK:
            tx.state = State.ROLLED_BACK.value
            return tx

        if action == RecoveryAction.REVERIFY:

            tx.verification_started = True
            tx.verification_completed = True
            tx.verification_passed = True

            tx.state = State.COMMITTING.value
            tx.commit_started = True
            tx.persisted = True

            if not tx.commit_completed:
                tx.commit_completed = True

                if tx.commit_count == 0:
                    tx.commit_count = 1

            tx.state = State.COMMITTED.value
            return tx

        if action == RecoveryAction.RECOVER:

            tx.verification_started = True
            tx.verification_completed = True
            tx.verification_passed = True

            tx.commit_started = True
            tx.persisted = True

            if not tx.commit_completed:
                tx.commit_completed = True

                if tx.commit_count == 0:
                    tx.commit_count = 1

            tx.state = State.COMMITTED.value
            return tx

        tx.state = State.QUARANTINED.value
        return tx

    def recover(self):

        tx = self.journal.load()
        action = self.decide(tx)

        tx = self.execute(
            tx,
            action,
        )

        self.journal.save(tx)

        return tx, action


def create_committed_transaction():

    payload = {
        "value": 123,
    }

    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    return Transaction(
        transaction_id="tx-idempotency-001",
        idempotency_key="idem-001",
        state=State.COMMITTED.value,
        payload_hash=hashlib.sha256(raw).hexdigest(),
        result_hash=hashlib.sha256(
            b"result-123"
        ).hexdigest(),
        write_started=True,
        write_completed=True,
        verification_started=True,
        verification_completed=True,
        verification_passed=True,
        commit_started=True,
        commit_completed=True,
        persisted=True,
        recovery_count=0,
        commit_count=1,
    )


def create_rollback_transaction():

    payload = {
        "value": 456,
    }

    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    return Transaction(
        transaction_id="tx-rollback-001",
        idempotency_key="idem-rollback-001",
        state=State.ROLLED_BACK.value,
        payload_hash=hashlib.sha256(raw).hexdigest(),
        recovery_count=0,
        commit_count=0,
    )
