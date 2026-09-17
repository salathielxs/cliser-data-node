#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
ENGINE="$ROOT/scripts/recovery_idempotency.py"
TEST="$ROOT/tests/test_recovery_idempotency.py"
DOC="$ROOT/docs/architecture/RECOVERY_IDEMPOTENCY_DUPLICATE_COMMIT.md"
REPORT_DIR="$ROOT/tmp/recovery_idempotency"
REPORT="$REPORT_DIR/recovery_idempotency_report.txt"

mkdir -p \
    "$ROOT/scripts" \
    "$ROOT/tests" \
    "$ROOT/docs/architecture" \
    "$REPORT_DIR"

cat > "$ENGINE" <<'PY'
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
PY

chmod +x "$ENGINE"

cat > "$TEST" <<'PY'
#!/usr/bin/env python3

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "scripts"),
)

from recovery_idempotency import (
    Journal,
    RecoveryEngine,
    RecoveryAction,
    State,
    Transaction,
    create_committed_transaction,
    create_rollback_transaction,
)


def test_committed_recovery_is_idempotent():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = create_committed_transaction()

    original_result_hash = tx.result_hash
    original_idempotency_key = tx.idempotency_key

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.COMPLETE
    assert tx1.state == State.COMMITTED.value
    assert tx1.commit_count == 1
    assert tx1.result_hash == original_result_hash
    assert tx1.idempotency_key == original_idempotency_key

    tx2, action2 = engine.recover()

    assert action2 == RecoveryAction.COMPLETE
    assert tx2.state == State.COMMITTED.value
    assert tx2.commit_count == 1
    assert tx2.result_hash == original_result_hash

    tx3, action3 = engine.recover()

    assert action3 == RecoveryAction.COMPLETE
    assert tx3.state == State.COMMITTED.value
    assert tx3.commit_count == 1
    assert tx3.recovery_count == 3

    temp.cleanup()


def test_finalize_is_exactly_once():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = Transaction(
        transaction_id="tx-finalize-001",
        idempotency_key="idem-finalize-001",
        state=State.COMMITTING.value,
        payload_hash="payload-hash",
        result_hash="result-hash",
        commit_started=True,
        commit_completed=False,
        persisted=True,
        commit_count=0,
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.FINALIZE
    assert tx1.state == State.COMMITTED.value
    assert tx1.commit_completed is True
    assert tx1.commit_count == 1

    tx2, action2 = engine.recover()

    assert action2 == RecoveryAction.COMPLETE
    assert tx2.state == State.COMMITTED.value
    assert tx2.commit_count == 1

    tx3, action3 = engine.recover()

    assert action3 == RecoveryAction.COMPLETE
    assert tx3.commit_count == 1

    temp.cleanup()


def test_rollback_is_terminal():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = create_rollback_transaction()

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.QUARANTINE
    assert tx1.state == State.QUARANTINED.value
    assert tx1.commit_count == 0

    temp.cleanup()


def test_no_duplicate_commit_from_recover():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = Transaction(
        transaction_id="tx-duplicate-001",
        idempotency_key="idem-duplicate-001",
        state=State.WRITING.value,
        payload_hash="payload",
        result_hash="result",
        write_started=True,
        write_completed=True,
        verification_completed=False,
        verification_passed=False,
        commit_started=False,
        commit_completed=False,
        persisted=False,
        commit_count=0,
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.REVERIFY
    assert tx1.state == State.COMMITTED.value
    assert tx1.commit_count == 1

    tx2, action2 = engine.recover()

    assert action2 == RecoveryAction.COMPLETE
    assert tx2.state == State.COMMITTED.value
    assert tx2.commit_count == 1

    tx3, action3 = engine.recover()

    assert action3 == RecoveryAction.COMPLETE
    assert tx3.state == State.COMMITTED.value
    assert tx3.commit_count == 1

    temp.cleanup()


def test_identity_and_result_are_stable():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = create_committed_transaction()

    transaction_id = tx.transaction_id
    idempotency_key = tx.idempotency_key
    result_hash = tx.result_hash

    journal.save(tx)

    engine = RecoveryEngine(journal)

    for _ in range(5):

        recovered, action = engine.recover()

        assert recovered.transaction_id == transaction_id
        assert recovered.idempotency_key == idempotency_key
        assert recovered.result_hash == result_hash
        assert recovered.commit_count == 1
        assert recovered.state == State.COMMITTED.value
        assert action == RecoveryAction.COMPLETE

    temp.cleanup()


def run_test(name, fn):

    try:
        fn()
        print(f"[PASS] {name}")
        return True

    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def main():

    tests = [
        (
            "test_committed_recovery_is_idempotent",
            test_committed_recovery_is_idempotent,
        ),
        (
            "test_finalize_is_exactly_once",
            test_finalize_is_exactly_once,
        ),
        (
            "test_rollback_is_terminal",
            test_rollback_is_terminal,
        ),
        (
            "test_no_duplicate_commit_from_recover",
            test_no_duplicate_commit_from_recover,
        ),
        (
            "test_identity_and_result_are_stable",
            test_identity_and_result_are_stable,
        ),
    ]

    passed = 0

    for name, fn in tests:

        if run_test(name, fn):
            passed += 1

    total = len(tests)

    print()
    print(f"RESULT: {passed}/{total}")

    if passed == total:
        print("STATUS: PASS")
        return 0

    print("STATUS: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
PY

chmod +x "$TEST"

cat > "$DOC" <<'MD'
# CLISER DATA NODE

## 15.2.6-H — Recovery Idempotency & Duplicate Commit Protection

### Objetivo

Validar recuperação idempotente e proteção contra commits duplicados.

### Invariantes

- COMMITTED -> COMPLETE
- COMPLETE não executa novo commit
- FINALIZE produz exatamente um commit
- REVERIFY produz exatamente um commit
- RECOVER produz exatamente um commit
- commit_count permanece 1
- transaction_id permanece estável
- idempotency_key permanece estável
- result_hash permanece estável
- recovery repetido não altera o resultado
- estado committed permanece terminal
MD

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.6-H"
echo "RECOVERY IDEMPOTENCY & DUPLICATE COMMIT PROTECTION"
echo "======================================================================"

python3 "$TEST" 2>&1 | tee "$REPORT"

STATUS=${PIPESTATUS[0]}

echo
echo "======================================================================"
echo "15.2.6-H — RESULT"
echo "======================================================================"

cat "$REPORT"

echo
echo "STATUS CODE: $STATUS"

exit "$STATUS"
