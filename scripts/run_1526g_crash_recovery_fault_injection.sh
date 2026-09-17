#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

DOC_DIR="$ROOT/docs/architecture"
SCRIPT_DIR="$ROOT/scripts"
TEST_DIR="$ROOT/tests"
TMP_DIR="$ROOT/tmp/crash_recovery"

DOC="$DOC_DIR/CRASH_RECOVERY_FAULT_INJECTION.md"
ENGINE="$SCRIPT_DIR/crash_recovery_fault_injection.py"
TEST="$TEST_DIR/test_crash_recovery_fault_injection.py"
RESULT="$TMP_DIR/crash_recovery_report.txt"

mkdir -p "$DOC_DIR"
mkdir -p "$SCRIPT_DIR"
mkdir -p "$TEST_DIR"
mkdir -p "$TMP_DIR"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.6-G"
echo "CRASH RECOVERY & FAULT INJECTION"
echo "======================================================================"
echo

# ----------------------------------------------------------------------
# G.1 — FAULT MODEL
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


        # Write never completed.
        if (
            tx.state == State.WRITING.value
            and not tx.write_completed
        ):

            return RecoveryAction.ROLLBACK


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
PY

chmod +x "$ENGINE"

echo "[OK] Fault Injection Engine criado:"
echo "     $ENGINE"
echo

# ----------------------------------------------------------------------
# G.2 — AUTOMATED TESTS
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

from crash_recovery_fault_injection import (
    FaultPoint,
    Journal,
    FaultInjector,
    TransactionProcessor,
    RecoveryEngine,
    State,
)


def run_case(fault):

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    processor = TransactionProcessor(
        journal,
        FaultInjector(fault),
    )

    tx = processor.create(
        "tx_test",
        {
            "value": 123,
        },
    )

    crashed = False

    try:

        processor.execute(tx)

    except RuntimeError as exc:

        assert str(exc).startswith(
            "INJECTED_CRASH:"
        )

        crashed = True

    recovered, action = RecoveryEngine(
        journal
    ).recover()

    temp.cleanup()

    return crashed, recovered, action


def test_after_prepared():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_PREPARED
    )

    assert crashed
    assert action.value == "ROLLBACK"
    assert tx.state == State.ROLLED_BACK.value


def test_during_write():

    crashed, tx, action = run_case(
        FaultPoint.DURING_WRITE
    )

    assert crashed
    assert action.value == "ROLLBACK"
    assert tx.state == State.ROLLED_BACK.value


def test_after_write():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_WRITE
    )

    assert crashed
    assert action.value == "REVERIFY"
    assert tx.state == State.COMMITTED.value


def test_during_verify():

    crashed, tx, action = run_case(
        FaultPoint.DURING_VERIFY
    )

    assert crashed
    assert action.value == "REVERIFY"
    assert tx.state == State.COMMITTED.value


def test_after_verify():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_VERIFY
    )

    assert crashed
    assert action.value == "RECOVER"
    assert tx.state == State.COMMITTED.value


def test_during_commit():

    crashed, tx, action = run_case(
        FaultPoint.DURING_COMMIT
    )

    assert crashed
    assert action.value == "RECOVER"
    assert tx.state == State.COMMITTED.value


def test_after_commit():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_COMMIT
    )

    assert crashed
    assert action.value == "FINALIZE"
    assert tx.state == State.COMMITTED.value


def test_no_fault():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    processor = TransactionProcessor(
        journal
    )

    tx = processor.create(
        "tx_no_fault",
        {
            "value": 999,
        },
    )

    result = processor.execute(tx)

    assert result.state == State.COMMITTED.value
    assert result.commit_completed
    assert result.persisted

    temp.cleanup()


def main():

    tests = [
        test_after_prepared,
        test_during_write,
        test_after_write,
        test_during_verify,
        test_after_verify,
        test_during_commit,
        test_after_commit,
        test_no_fault,
    ]

    passed = 0

    for test in tests:

        try:

            test()

            print(
                f"[PASS] {test.__name__}"
            )

            passed += 1

        except Exception as exc:

            print(
                f"[FAIL] "
                f"{test.__name__}: {exc}"
            )

    print()
    print(
        f"RESULT: {passed}/{len(tests)}"
    )

    if passed != len(tests):

        raise SystemExit(1)


if __name__ == "__main__":

    main()
PY

chmod +x "$TEST"

echo "[OK] Fault Injection Tests criados:"
echo "     $TEST"
echo

# ----------------------------------------------------------------------
# G.3 — ARCHITECTURE DOCUMENT
# ----------------------------------------------------------------------

cat > "$DOC" <<'MD'
# CLISER DATA NODE

# 15.2.6-G — CRASH RECOVERY & FAULT INJECTION

## Objetivo

Validar o comportamento do Transaction Recovery Engine quando
uma transação sofre uma interrupção artificial em diferentes
pontos do lifecycle.

## Fault Points

### AFTER_PREPARED

Simula crash imediatamente após PREPARED.

Esperado:

PREPARED -> ROLLBACK

### DURING_WRITE

Simula interrupção durante WRITE.

Esperado:

WRITING incompleto -> ROLLBACK

### AFTER_WRITE

Simula crash após WRITE completo e antes da conclusão da verificação.

Esperado:

REVERIFY -> COMMITTED

### DURING_VERIFY

Simula interrupção durante VERIFY.

Esperado:

REVERIFY -> COMMITTED

### AFTER_VERIFY

Simula crash após verification concluída e antes de COMMIT.

Esperado:

RECOVER -> COMMITTED

### DURING_COMMIT

Simula interrupção após COMMIT iniciado, mas antes da persistência.

Esperado:

RECOVER -> COMMITTED

### AFTER_COMMIT

Simula interrupção após persistência do commit, mas antes do
marcador final de conclusão.

Esperado:

FINALIZE -> COMMITTED

## No Fault

Uma transação sem falha deve produzir:

NEW
 ->
PREPARED
 ->
WRITING
 ->
VERIFYING
 ->
COMMITTING
 ->
COMMITTED

## Invariantes

1. Uma transação não pode ser COMMITTED duas vezes.
2. Uma transação parcialmente escrita não deve ser considerada
   COMMITTED.
3. Uma transação com commit persistido deve ser finalizada.
4. Recovery deve ser idempotente.
5. O journal deve sobreviver ao restart.
6. Falhas devem produzir estado determinístico.
7. Estados desconhecidos devem ser isolados.
8. Nenhuma operação de commit deve ser repetida cegamente.

## Resultado

A etapa 15.2.6-G será considerada válida quando:

- todos os fault points forem executados;
- todos os testes passarem;
- cada crash possuir ação de recovery determinística;
- nenhuma transação terminar em estado inconsistente.
MD

echo "[OK] Documento criado:"
echo "     $DOC"
echo

# ----------------------------------------------------------------------
# G.4 — EXECUTION
# ----------------------------------------------------------------------

echo "======================================================================"
echo "EXECUTANDO FAULT-INJECTION TESTS"
echo "======================================================================"
echo

python3 "$TEST" | tee "$RESULT"

TEST_STATUS=${PIPESTATUS[0]}

echo
echo "======================================================================"
echo "RESULTADO 15.2.6-G"
echo "======================================================================"

if [ "$TEST_STATUS" -eq 0 ]; then

    echo "STATUS: PASS"
    echo "FAULT INJECTION: VALIDATED"

else

    echo "STATUS: FAIL"
    echo "FAULT INJECTION: REQUIRES CORRECTION"

fi

echo
echo "Arquivos:"
echo "  Engine : $ENGINE"
echo "  Tests  : $TEST"
echo "  Doc    : $DOC"
echo "  Report : $RESULT"
echo

exit "$TEST_STATUS"
