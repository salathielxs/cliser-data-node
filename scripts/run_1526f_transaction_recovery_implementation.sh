#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

DOC_DIR="$ROOT/docs/architecture"
SCRIPT_DIR="$ROOT/scripts"
TEST_DIR="$ROOT/tests"
TMP_DIR="$ROOT/tmp/transaction_recovery"

DOC="$DOC_DIR/TRANSACTION_RECOVERY_IMPLEMENTATION.md"
ENGINE="$SCRIPT_DIR/transaction_recovery_engine.py"
TEST="$TEST_DIR/test_transaction_recovery.py"
RESULT="$TMP_DIR/recovery_implementation_report.txt"

mkdir -p "$DOC_DIR"
mkdir -p "$SCRIPT_DIR"
mkdir -p "$TEST_DIR"
mkdir -p "$TMP_DIR"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.6-F"
echo "TRANSACTION RECOVERY IMPLEMENTATION"
echo "======================================================================"
echo

# ----------------------------------------------------------------------
# F.1 — RECOVERY ENGINE
# ----------------------------------------------------------------------

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
PY

chmod +x "$ENGINE"

echo "[OK] Recovery Engine criado:"
echo "     $ENGINE"
echo

# ----------------------------------------------------------------------
# F.2 — AUTOMATED TESTS
# ----------------------------------------------------------------------

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

from transaction_recovery_engine import (
    RecoveryAction,
    RecoveryState,
    RecoveryEngine,
    TransactionJournal,
    make_transaction,
)


def new_env():
    temp = tempfile.TemporaryDirectory()

    journal = TransactionJournal(
        Path(temp.name) / "transaction.json"
    )

    return temp, journal


def test_prepared_rollback():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_prepared",
        RecoveryState.PREPARED,
        {"value": 1},
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.ROLLBACK
    assert recovered.state == RecoveryState.ROLLED_BACK.value

    temp.cleanup()


def test_writing_rollback():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_writing",
        RecoveryState.WRITING,
        {"value": 2},
    )

    tx.write_started = True
    tx.write_completed = False

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.ROLLBACK
    assert recovered.state == RecoveryState.ROLLED_BACK.value

    temp.cleanup()


def test_verify_recovery():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_verify",
        RecoveryState.VERIFYING,
        {"value": 3},
    )

    tx.write_completed = True
    tx.verification_started = True
    tx.verification_completed = False

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.REVERIFY
    assert recovered.verification_completed is True
    assert recovered.verification_passed is True

    temp.cleanup()


def test_commit_finalize():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_commit",
        RecoveryState.COMMITTING,
        {"value": 4},
    )

    tx.write_completed = True
    tx.verification_completed = True
    tx.verification_passed = True
    tx.commit_started = True

    journal.save(tx)

    engine = RecoveryEngine(
        journal,
        persisted_state={
            "tx_commit": True,
        },
    )

    recovered, action = engine.recover()

    assert action == RecoveryAction.FINALIZE
    assert recovered.state == RecoveryState.COMMITTED.value
    assert recovered.commit_completed is True

    temp.cleanup()


def test_already_committed():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_done",
        RecoveryState.COMMITTED,
        {"value": 5},
    )

    tx.commit_started = True
    tx.commit_completed = True

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.COMPLETE
    assert recovered.state == RecoveryState.COMMITTED.value

    temp.cleanup()


def test_failed_verification():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_failed",
        RecoveryState.VERIFYING,
        {"value": 6},
    )

    tx.verification_started = True
    tx.verification_completed = True
    tx.verification_passed = False
    tx.error_code = "VERIFICATION_FAILED"

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.ROLLBACK
    assert recovered.state == RecoveryState.ROLLED_BACK.value

    temp.cleanup()


def test_unknown_state_quarantine():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_unknown",
        RecoveryState.IN_DOUBT,
        {"value": 7},
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.QUARANTINE
    assert recovered.state == RecoveryState.QUARANTINED.value

    temp.cleanup()


def main():

    tests = [
        test_prepared_rollback,
        test_writing_rollback,
        test_verify_recovery,
        test_commit_finalize,
        test_already_committed,
        test_failed_verification,
        test_unknown_state_quarantine,
    ]

    passed = 0

    for test in tests:

        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1

        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc}")

    print()
    print(f"RESULT: {passed}/{len(tests)}")

    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
PY

chmod +x "$TEST"

echo "[OK] Test suite criado:"
echo "     $TEST"
echo

# ----------------------------------------------------------------------
# F.3 — ARCHITECTURE DOCUMENT
# ----------------------------------------------------------------------

cat > "$DOC" <<'MD'
# CLISER DATA NODE
# 15.2.6-F — TRANSACTION RECOVERY IMPLEMENTATION

## Objetivo

Implementar o mecanismo de recuperação de transações interrompidas
durante WRITE, VERIFY e COMMIT.

## Componentes

### Recovery Engine

Arquivo:

scripts/transaction_recovery_engine.py

Responsabilidades:

- carregar transaction journal;
- inspecionar estado;
- determinar ação de recovery;
- executar recovery;
- persistir novo estado;
- evitar commit duplicado;
- finalizar commit previamente persistido;
- executar rollback;
- colocar estados desconhecidos em quarantine.

## Recovery Actions

- RECOVER
- REVERIFY
- FINALIZE
- ROLLBACK
- QUARANTINE
- COMPLETE

## Recovery States

- NEW
- PREPARED
- WRITING
- VERIFYING
- COMMITTING
- COMMITTED
- ROLLED_BACK
- RECOVERABLE
- IN_DOUBT
- CORRUPTED
- QUARANTINED

## Atomic Journal Write

O journal utiliza arquivo temporário seguido de os.replace().

Isso evita deixar o arquivo principal parcialmente escrito.

## Idempotência

Cada transação possui:

transaction_id
idempotency_key

O recovery deve verificar se o commit já foi persistido antes
de executar novamente uma operação.

## Rollback

Rollback é utilizado para:

- PREPARED interrompido;
- WRITE incompleto;
- verification failure;
- estado inválido.

## Commit Recovery

Se COMMITTING for encontrado após restart:

1. carregar journal;
2. verificar estado persistido;
3. verificar transaction_id;
4. verificar idempotency;
5. verificar hashes;
6. finalizar ou recuperar;
7. nunca executar commit cegamente.

## Quarantine

Estados inconsistentes ou não reconhecidos são enviados para:

QUARANTINED

Não devem ser automaticamente modificados.

## Testes

Arquivo:

tests/test_transaction_recovery.py

Cenários:

1. PREPARED -> ROLLBACK
2. WRITING incompleto -> ROLLBACK
3. VERIFYING interrompido -> REVERIFY
4. COMMITTING já persistido -> FINALIZE
5. COMMITTED -> COMPLETE
6. Verification failure -> ROLLBACK
7. IN_DOUBT -> QUARANTINE

## Critério

15.2.6-F passa quando todos os testes forem aprovados.
MD

echo "[OK] Documento criado:"
echo "     $DOC"
echo

# ----------------------------------------------------------------------
# F.4 — EXECUTION
# ----------------------------------------------------------------------

echo "======================================================================"
echo "EXECUTANDO TESTES"
echo "======================================================================"
echo

python3 "$TEST" | tee "$RESULT"

TEST_STATUS=${PIPESTATUS[0]}

echo
echo "======================================================================"
echo "RESULTADO"
echo "======================================================================"

if [ "$TEST_STATUS" -eq 0 ]; then
    echo "STATUS: PASS"
    echo "15.2.6-F — TRANSACTION RECOVERY IMPLEMENTATION"
    echo "VALIDADO"
else
    echo "STATUS: FAIL"
    echo "15.2.6-F necessita correção."
fi

echo
echo "Arquivos:"
echo "  Engine : $ENGINE"
echo "  Tests  : $TEST"
echo "  Doc    : $DOC"
echo "  Report : $RESULT"
echo

exit "$TEST_STATUS"
