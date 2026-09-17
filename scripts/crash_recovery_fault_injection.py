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


class FaultPoint(str, Enum):

    NONE = "NONE"

    AFTER_PREPARED = "AFTER_PREPARED"
    DURING_WRITE = "DURING_WRITE"
    AFTER_WRITE = "AFTER_WRITE"

    DURING_VERIFY = "DURING_VERIFY"
    AFTER_VERIFY = "AFTER_VERIFY"

    DURING_COMMIT = "DURING_COMMIT"
    AFTER_COMMIT = "AFTER_COMMIT"


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

    error_code: str | None = None


def payload_hash(payload: object) -> str:

    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()

    return hashlib.sha256(raw).hexdigest()


def result_hash(payload_hash_value: str) -> str:

    raw = (
        "result:" + payload_hash_value
    ).encode()

    return hashlib.sha256(raw).hexdigest()


class Journal:

    def __init__(self, path: str | Path):

        self.path = Path(path)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )


    def save(self, transaction: Transaction):

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
                    asdict(transaction),
                    handle,
                    indent=2,
                    sort_keys=True,
                )

                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                tmp,
                self.path,
            )

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


class FaultInjector:

    def __init__(
        self,
        fault: FaultPoint = FaultPoint.NONE,
    ):

        self.fault = fault


    def crash_if(
        self,
        point: FaultPoint,
    ):

        if self.fault == point:

            raise RuntimeError(
                f"INJECTED_CRASH:{point.value}"
            )


class TransactionProcessor:

    def __init__(
        self,
        journal: Journal,
        injector: FaultInjector | None = None,
    ):

        self.journal = journal

        self.injector = (
            injector
            or FaultInjector()
        )


    def create(
        self,
        transaction_id: str,
        payload: object,
    ) -> Transaction:

        return Transaction(
            transaction_id=transaction_id,
            idempotency_key=(
                f"idem_{transaction_id}"
            ),
            state=State.NEW.value,
            payload_hash=payload_hash(payload),
        )


    def persist(self, tx: Transaction):

        self.journal.save(tx)


    def execute(
        self,
        tx: Transaction,
    ):

        # --------------------------------------------------------------
        # PREPARE
        # --------------------------------------------------------------

        tx.state = State.PREPARED.value

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.AFTER_PREPARED
        )

        # --------------------------------------------------------------
        # WRITE
        # --------------------------------------------------------------

        tx.state = State.WRITING.value
        tx.write_started = True

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.DURING_WRITE
        )

        tx.write_completed = True

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.AFTER_WRITE
        )

        # --------------------------------------------------------------
        # VERIFY
        # --------------------------------------------------------------

        tx.state = State.VERIFYING.value
        tx.verification_started = True

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.DURING_VERIFY
        )

        tx.verification_completed = True
        tx.verification_passed = True

        if tx.result_hash is None:
            tx.result_hash = result_hash(
                tx.payload_hash
            )

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.AFTER_VERIFY
        )

        # --------------------------------------------------------------
        # COMMIT
        # --------------------------------------------------------------

        tx.state = State.COMMITTING.value
        tx.commit_started = True

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.DURING_COMMIT
        )

        tx.persisted = True

        self.persist(tx)

        self.injector.crash_if(
            FaultPoint.AFTER_COMMIT
        )

        tx.commit_completed = True
        tx.state = State.COMMITTED.value

        self.persist(tx)

        return tx


class RecoveryEngine:

    def __init__(
        self,
        journal: Journal,
    ):

        self.journal = journal


    def decide(
        self,
        tx: Transaction,
    ) -> RecoveryAction:

        # Already committed.
        if (
            tx.state == State.COMMITTED.value
            and tx.commit_completed
        ):

            return RecoveryAction.COMPLETE


        # Commit persisted but completion marker was
        # not written before crash.
        if (
            tx.commit_started
            and tx.persisted
        ):

            return RecoveryAction.FINALIZE


        # PREPARED means the transaction has not started
        # writing yet. Nothing needs to be preserved.
        if tx.state == State.PREPARED.value:

            return RecoveryAction.ROLLBACK


        # Write never completed.
        if (
            tx.state == State.WRITING.value
            and not tx.write_completed
        ):

            return RecoveryAction.ROLLBACK


        # Write completed but verification never started.
        # The durable write must be verified before commit.
        if (
            tx.state == State.WRITING.value
            and tx.write_completed
            and not tx.verification_completed
        ):

            return RecoveryAction.REVERIFY


        # Verification was interrupted.
        if (
            tx.state == State.VERIFYING.value
            and not tx.verification_completed
        ):

            return RecoveryAction.REVERIFY


        # Commit started but nothing was persisted.
        if (
            tx.state == State.COMMITTING.value
            and not tx.persisted
        ):

            return RecoveryAction.RECOVER


        # Safe completed transaction.
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
    ):

        tx.recovery_count += 1


        if action == RecoveryAction.COMPLETE:

            tx.state = State.COMMITTED.value

            return tx


        if action == RecoveryAction.FINALIZE:

            tx.commit_completed = True
            tx.state = State.COMMITTED.value

            return tx


        if action == RecoveryAction.ROLLBACK:

            tx.state = State.ROLLED_BACK.value

            return tx


        if action == RecoveryAction.REVERIFY:

            tx.verification_started = True
            tx.verification_completed = True
            tx.verification_passed = True

            if tx.result_hash is None:
                tx.result_hash = result_hash(
                    tx.payload_hash
                )

            tx.state = State.COMMITTING.value
            tx.commit_started = True

            tx.persisted = True
            tx.commit_completed = True

            tx.state = State.COMMITTED.value

            return tx


        if action == RecoveryAction.RECOVER:

            tx.verification_started = True
            tx.verification_completed = True
            tx.verification_passed = True

            if tx.result_hash is None:
                tx.result_hash = result_hash(
                    tx.payload_hash
                )

            tx.commit_started = True
            tx.persisted = True
            tx.commit_completed = True

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


def run_fault(
    root: Path,
    fault: FaultPoint,
):

    journal = Journal(
        root / f"{fault.value}.json"
    )

    processor = TransactionProcessor(
        journal,
        FaultInjector(fault),
    )

    tx = processor.create(
        f"tx_{fault.value.lower()}",
        {
            "object": "test",
            "value": 100,
        },
    )

    crashed = False

    try:

        processor.execute(tx)

    except RuntimeError as exc:

        if str(exc).startswith(
            "INJECTED_CRASH:"
        ):

            crashed = True

        else:

            raise

    recovery = RecoveryEngine(journal)

    recovered, action = recovery.recover()

    return {
        "fault": fault.value,
        "crashed": crashed,
        "recovery_action": action.value,
        "final_state": recovered.state,
        "persisted": recovered.persisted,
        "commit_completed": (
            recovered.commit_completed
        ),
        "recovery_count": (
            recovered.recovery_count
        ),
    }


def main():

    root = Path(
        tempfile.mkdtemp(
            prefix="cliser_1526g_"
        )
    )

    faults = [
        FaultPoint.AFTER_PREPARED,
        FaultPoint.DURING_WRITE,
        FaultPoint.AFTER_WRITE,
        FaultPoint.DURING_VERIFY,
        FaultPoint.AFTER_VERIFY,
        FaultPoint.DURING_COMMIT,
        FaultPoint.AFTER_COMMIT,
    ]

    results = []

    for fault in faults:

        result = run_fault(
            root,
            fault,
        )

        results.append(result)

        print(
            json.dumps(
                result,
                sort_keys=True,
            )
        )

    print()
    print(
        json.dumps(
            {
                "faults_tested": len(results),
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":

    main()
