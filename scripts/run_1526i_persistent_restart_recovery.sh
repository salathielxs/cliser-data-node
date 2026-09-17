#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
TEST="$ROOT/tests/test_persistent_restart_recovery.py"
DOC="$ROOT/docs/architecture/PERSISTENT_RESTART_RECOVERY.md"
REPORT_DIR="$ROOT/tmp/persistent_restart_recovery"
REPORT="$REPORT_DIR/persistent_restart_recovery_report.txt"

mkdir -p "$ROOT/tests" "$ROOT/docs/architecture" "$REPORT_DIR"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.6-I"
echo "PERSISTENT RECOVERY JOURNAL & RESTART RECOVERY"
echo "======================================================================"

cat > "$TEST" <<'PY'
#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / "scripts"))

from crash_recovery_fault_injection import (
    FaultInjector,
    FaultPoint,
    Journal,
    RecoveryEngine,
    TransactionProcessor,
)


def run_process(script, journal_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "scripts")

    return subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(journal_path),
        ],
        capture_output=True,
        text=True,
        env=env,
    )


def produce(journal_path, tx_id, value, fault):
    script = f'''
import sys
from pathlib import Path
from crash_recovery_fault_injection import (
    FaultInjector,
    FaultPoint,
    Journal,
    TransactionProcessor,
)

journal = Journal(Path(sys.argv[1]))

processor = TransactionProcessor(
    journal,
    FaultInjector(FaultPoint.{fault}),
)

tx = processor.create("{tx_id}", {{"value": {value}}})
processor.execute(tx)
'''

    return run_process(script, journal_path)


def recover(journal_path):
    script = r'''
import sys
from pathlib import Path
from crash_recovery_fault_injection import Journal, RecoveryEngine

journal = Journal(Path(sys.argv[1]))
tx, action = RecoveryEngine(journal).recover()

print(tx.state.value)
print(action.value)
print(tx.commit_count)
print(tx.transaction_id)
print(tx.idempotency_key)
print(tx.payload_hash)
print(tx.result_hash or "")
'''

    return run_process(script, journal_path)


def test_journal_survives_process_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_001",
            123,
            "AFTER_PREPARED",
        )

        assert result.returncode == 0, result.stderr
        assert path.exists()

        data = json.loads(path.read_text())

        assert data["transaction_id"] == "tx_restart_001"
        assert data["state"] == "PREPARED"
        assert data["persisted"] is True


def test_restart_prepared():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(path, "tx_restart_002", 456, "AFTER_PREPARED")
        assert result.returncode == 0, result.stderr

        result = recover(path)
        assert result.returncode == 0, result.stderr

        lines = result.stdout.strip().splitlines()

        assert lines[0] == "ROLLED_BACK"
        assert lines[1] == "ROLLBACK"


def test_restart_after_write():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(path, "tx_restart_003", 789, "AFTER_WRITE")
        assert result.returncode == 0, result.stderr

        result = recover(path)
        assert result.returncode == 0, result.stderr

        lines = result.stdout.strip().splitlines()

        assert lines[0] == "VERIFYING"
        assert lines[1] == "REVERIFY"


def test_restart_after_verify():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(path, "tx_restart_004", 999, "AFTER_VERIFY")
        assert result.returncode == 0, result.stderr

        result = recover(path)
        assert result.returncode == 0, result.stderr

        lines = result.stdout.strip().splitlines()

        assert lines[0] == "COMMITTED"
        assert lines[1] == "RECOVER"


def test_restart_after_commit_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(path, "tx_restart_005", 111, "AFTER_COMMIT")
        assert result.returncode == 0, result.stderr

        result = recover(path)
        assert result.returncode == 0, result.stderr

        first = result.stdout.strip().splitlines()

        assert first[0] == "COMMITTED"
        assert first[2] == "1"

        result_hash = first[6]

        result = recover(path)
        assert result.returncode == 0, result.stderr

        second = result.stdout.strip().splitlines()

        assert second[0] == "COMMITTED"
        assert second[1] == "COMPLETE"
        assert second[2] == "1"
        assert second[6] == result_hash


def test_identity_survives_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(path, "tx_restart_006", 222, "AFTER_VERIFY")
        assert result.returncode == 0, result.stderr

        before = json.loads(path.read_text())

        result = recover(path)
        assert result.returncode == 0, result.stderr

        lines = result.stdout.strip().splitlines()

        assert lines[3] == before["transaction_id"]
        assert lines[4] == before["idempotency_key"]
        assert lines[5] == before["payload_hash"]

        after = json.loads(path.read_text())

        assert after["transaction_id"] == before["transaction_id"]
        assert after["idempotency_key"] == before["idempotency_key"]
        assert after["payload_hash"] == before["payload_hash"]


def test_atomic_journal_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        script = r'''
import sys
from pathlib import Path
from crash_recovery_fault_injection import (
    FaultInjector,
    FaultPoint,
    Journal,
    TransactionProcessor,
)

journal = Journal(Path(sys.argv[1]))

processor = TransactionProcessor(
    journal,
    FaultInjector(FaultPoint.NONE),
)

tx = processor.create("tx_restart_007", {"value": 333})
processor.execute(tx)
'''

        result = run_process(script, path)

        assert result.returncode == 0, result.stderr
        assert path.exists()

        data = json.loads(path.read_text())

        assert isinstance(data, dict)
        assert data["transaction_id"] == "tx_restart_007"
        assert data["state"] == "COMMITTED"


def main():
    tests = [
        test_journal_survives_process_restart,
        test_restart_prepared,
        test_restart_after_write,
        test_restart_after_verify,
        test_restart_after_commit_idempotent,
        test_identity_survives_restart,
        test_atomic_journal_json,
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

    if passed == len(tests):
        print("STATUS: PASS")
        return 0

    print("STATUS: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
PY

cat > "$DOC" <<'MD'
# CLISER DATA NODE
# 15.2.6-I — Persistent Recovery Journal & Restart Recovery

## Objective

Validate transaction recovery across independent Python processes.

## Scope

- Persistent journal
- Cross-process recovery
- PREPARED recovery
- WRITING recovery
- VERIFYING recovery
- COMMITTED restart behavior
- Duplicate commit protection
- Identity preservation
- Payload hash preservation
- Atomic JSON journal

## Invariant

A committed transaction must remain idempotent after process restart.

Expected:

    commit_count == 1

Repeated recovery must not create another commit.

## Validation

Expected automated result:

    RESULT: 7/7
    STATUS: PASS
MD

python3 "$TEST" | tee "$REPORT"

STATUS=${PIPESTATUS[0]}

echo
echo "======================================================================"
echo "15.2.6-I — RESULT"
echo "======================================================================"

if [ "$STATUS" -eq 0 ]; then
    echo "[PASS] Persistent journal"
    echo "[PASS] Cross-process recovery"
    echo "[PASS] Restart idempotency"
    echo "[PASS] Journal integrity"
    echo
    echo "RESULT: 7/7"
    echo "STATUS: PASS"
else
    echo "[FAIL] Persistent restart recovery"
    echo
    echo "STATUS: FAIL"
fi

echo
echo "REPORT: $REPORT"

exit "$STATUS"
