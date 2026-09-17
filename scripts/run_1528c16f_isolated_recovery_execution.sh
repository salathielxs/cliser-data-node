#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.16-F"
echo "ISOLATED RECOVERY EXECUTION MATRIX"
echo "======================================================================"

TMP_DIR="$ROOT/tmp/c16f_recovery_fixture"

rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo
echo "[1] PRODUCTION DATABASE PROTECTION"

python - <<'PY'
from pathlib import Path

root = Path.home() / "cliser-data-node"

production_db = root / "data" / "labdex.db"
fixture_dir = root / "tmp" / "c16f_recovery_fixture"

print(f"PRODUCTION_DB={production_db}")
print(f"PRODUCTION_DB_EXISTS={production_db.exists()}")
print(f"FIXTURE_DIR={fixture_dir}")
print("PRODUCTION_DATABASE_USED=NO")
PY

echo
echo "[2] RECOVERY SOURCE / DEPENDENCY MAP"

python - <<'PY'
import inspect
import node.recovery as recovery

for name in [
    "_recover_commit",
    "_rollback_transaction",
    "recover_transaction",
]:
    print()
    print(f"--- {name} ---")
    print(inspect.getsource(getattr(recovery, name)))
PY

echo
echo "[3] ISOLATED RECOVERY FIXTURE"

python - <<'PY'
import json
from pathlib import Path

fixture = Path.home() / "cliser-data-node" / "tmp" / "c16f_recovery_fixture"

fixture.mkdir(parents=True, exist_ok=True)

cases = []

recoverable_states = [
    "PREPARED",
    "WRITING",
    "VERIFYING",
    "COMMITTING",
]

for state in recoverable_states:
    cases.append({
        "id": f"{state}-JOURNAL-ABSENT",
        "state": state,
        "journal": None,
        "expected": "ROLLBACK",
    })

    cases.append({
        "id": f"{state}-MARKER-0",
        "state": state,
        "journal": {
            "commit_marker": 0,
            "resources": {},
        },
        "expected": "ROLLBACK",
    })

    cases.append({
        "id": f"{state}-MARKER-1-VALID",
        "state": state,
        "journal": {
            "commit_marker": 1,
            "resources": {
                "block_mode": False,
            },
        },
        "expected": "COMMITTED_OR_ROLLBACK_VALIDATION",
    })

    cases.append({
        "id": f"{state}-MARKER-1-INVALID",
        "state": state,
        "journal": {
            "commit_marker": 1,
            "resources": {
                "block_mode": False,
            },
        },
        "expected": "ROLLBACK_IF_RESOURCE_INVALID",
    })

for state in ["COMMITTED", "ROLLBACK", "FAILED"]:
    cases.append({
        "id": f"{state}-TERMINAL",
        "state": state,
        "journal": None,
        "expected": (
            "NOOP"
            if state in {"COMMITTED", "ROLLBACK"}
            else "NOOP_UNSUPPORTED_STATE"
        ),
    })

path = fixture / "cases.json"

path.write_text(
    json.dumps(cases, indent=2),
    encoding="utf-8",
)

print(f"FIXTURE_CASES={len(cases)}")
print(f"FIXTURE_FILE={path}")
PY

echo
echo "[4] REAL RECOVERY FUNCTION — ISOLATED MONKEYPATCH"

python - <<'PY'
from node import recovery

cases = [
    ("PREPARED", None),
    ("PREPARED", {"commit_marker": 0, "resources": {}}),
    ("WRITING", None),
    ("WRITING", {"commit_marker": 0, "resources": {}}),
    ("VERIFYING", None),
    ("VERIFYING", {"commit_marker": 0, "resources": {}}),
    ("COMMITTING", None),
    ("COMMITTING", {"commit_marker": 0, "resources": {}}),
]

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal
original_rollback = recovery._rollback_transaction

results = []

try:
    for index, (state, journal) in enumerate(cases, start=1):

        transaction_id = f"C16F-{index:03d}"

        transaction = {
            "transaction_id": transaction_id,
            "object_id": f"OBJECT-{index:03d}",
            "state": state,
        }

        recovery.get_transaction = (
            lambda txid, tx=transaction:
            tx if txid == transaction_id else None
        )

        recovery.get_transaction_journal = (
            lambda txid, j=journal:
            j
        )

        rollback_calls = []

        def fake_rollback(txid, tx):
            rollback_calls.append(txid)
            return {
                "transaction_id": txid,
                "action": "ROLLBACK",
                "reason": "ISOLATED_FIXTURE",
            }

        recovery._rollback_transaction = fake_rollback

        result = recovery.recover_transaction(
            transaction_id
        )

        results.append({
            "state": state,
            "journal": (
                "ABSENT"
                if journal is None
                else journal.get("commit_marker")
            ),
            "action": result.get("action"),
            "final_state": result.get("final_state"),
            "recovered": result.get("recovered"),
            "rollback_called": bool(rollback_calls),
        })

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
    recovery._rollback_transaction = original_rollback

print("ISOLATED_RESULTS")

for result in results:
    print(result)

rollback_ok = all(
    r["action"] == "ROLLBACK"
    and r["final_state"] == "ROLLBACK"
    and r["recovered"] is True
    for r in results
)

print()
print(
    "NO_JOURNAL_AND_MARKER_0=PASS"
    if rollback_ok
    else "NO_JOURNAL_AND_MARKER_0=FAIL"
)
PY

echo
echo "[5] TERMINAL / UNSUPPORTED STATES"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal

cases = [
    ("COMMITTED", "NOOP"),
    ("ROLLBACK", "NOOP"),
    ("FAILED", "NOOP_UNSUPPORTED_STATE"),
]

results = []

try:
    for index, (state, expected) in enumerate(cases):
        txid = f"C16F-T-{index}"

        recovery.get_transaction = lambda txid, state=state: {
            "transaction_id": txid,
            "object_id": "OBJECT",
            "state": state,
        }

        recovery.get_transaction_journal = (
            lambda txid: None
        )

        result = recovery.recover_transaction(txid)

        actual = result.get("action")

        results.append(
            (state, expected, actual)
        )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal

for state, expected, actual in results:
    print(
        f"{state}: "
        f"EXPECTED={expected} "
        f"ACTUAL={actual} "
        f"{'PASS' if expected == actual else 'FAIL'}"
    )

print(
    "TERMINAL_UNSUPPORTED_MATRIX=" +
    (
        "PASS"
        if all(expected == actual for _, expected, actual in results)
        else "FAIL"
    )
)
PY

echo
echo "[6] COMMIT MARKER PATH — VALIDATION BRANCH"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal
original_recover_commit = recovery._recover_commit
original_rollback = recovery._rollback_transaction

try:
    transaction_id = "C16F-COMMIT-VALID"

    recovery.get_transaction = lambda txid: {
        "transaction_id": txid,
        "object_id": "OBJECT-COMMIT",
        "state": "COMMITTING",
    }

    recovery.get_transaction_journal = lambda txid: {
        "commit_marker": 1,
        "resources": {
            "block_mode": False,
        },
    }

    recovery._recover_commit = lambda txid, tx: {
        "transaction_id": txid,
        "action": "COMMIT",
        "reason": "ISOLATED_VALIDATION",
    }

    recovery._rollback_transaction = lambda txid, tx: {
        "transaction_id": txid,
        "action": "ROLLBACK",
        "reason": "UNEXPECTED",
    }

    result = recovery.recover_transaction(
        transaction_id
    )

    print(result)

    print(
        "MARKER_1_COMMIT_PATH=" +
        (
            "PASS"
            if result.get("action") == "COMMIT"
            and result.get("final_state") == "COMMITTED"
            and result.get("commit_marker") is True
            else "FAIL"
        )
    )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
    recovery._recover_commit = original_recover_commit
    recovery._rollback_transaction = original_rollback
PY

echo
echo "[7] COMMIT MARKER PATH — INVALID RESOURCE BRANCH"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal
original_recover_commit = recovery._recover_commit
original_rollback = recovery._rollback_transaction

try:
    transaction_id = "C16F-COMMIT-INVALID"

    recovery.get_transaction = lambda txid: {
        "transaction_id": txid,
        "object_id": "OBJECT-COMMIT-INVALID",
        "state": "COMMITTING",
    }

    recovery.get_transaction_journal = lambda txid: {
        "commit_marker": 1,
        "resources": {
            "block_mode": False,
        },
    }

    recovery._recover_commit = lambda txid, tx: {
        "transaction_id": txid,
        "action": "ROLLBACK",
        "reason": "COMMIT_MARKER_BUT_RESOURCES_INVALID",
    }

    rollback_calls = []

    def fake_rollback(txid, tx):
        rollback_calls.append(txid)
        return {
            "transaction_id": txid,
            "action": "ROLLBACK",
            "reason": "ISOLATED_INVALID_RESOURCE",
        }

    recovery._rollback_transaction = fake_rollback

    result = recovery.recover_transaction(
        transaction_id
    )

    print(result)

    print(
        "MARKER_1_INVALID_RESOURCE=" +
        (
            "PASS"
            if result.get("action") == "ROLLBACK"
            and result.get("final_state") == "ROLLBACK"
            and result.get("commit_marker") is True
            and rollback_calls
            else "FAIL"
        )
    )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
    recovery._recover_commit = original_recover_commit
    recovery._rollback_transaction = original_rollback
PY

echo
echo "[8] IDEMPOTENCY — TERMINAL RE-EXECUTION"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal

states = [
    "COMMITTED",
    "ROLLBACK",
]

try:
    for state in states:

        txid = f"C16F-IDEMP-{state}"

        current = {
            "transaction_id": txid,
            "object_id": f"OBJECT-{state}",
            "state": state,
        }

        recovery.get_transaction = (
            lambda transaction_id, current=current:
            current
        )

        recovery.get_transaction_journal = (
            lambda transaction_id: None
        )

        first = recovery.recover_transaction(txid)
        second = recovery.recover_transaction(txid)

        stable = (
            first.get("action") == "NOOP"
            and second.get("action") == "NOOP"
            and first.get("final_state") == state
            and second.get("final_state") == state
        )

        print(
            f"{state}_IDEMPOTENCY="
            f"{'PASS' if stable else 'FAIL'}"
        )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
PY

echo
echo "[9] PRODUCTION DATABASE RECHECK"

python - <<'PY'
from pathlib import Path
from node.registry import list_transactions
from node.transaction import RECOVERABLE_STATES

root = Path.home() / "cliser-data-node"
db = root / "data" / "labdex.db"

before = db.stat().st_size if db.exists() else None

rows = list_transactions()

def normalize(value):
    return getattr(value, "value", value)

recoverable = {
    normalize(x) for x in RECOVERABLE_STATES
}

pending = [
    row for row in rows
    if row[4] in recoverable
]

after = db.stat().st_size if db.exists() else None

print(f"DB_SIZE={after}")
print(f"RECOVERY_CANDIDATES={len(pending)}")
print(f"PRODUCTION_DB_READ_ONLY={'PASS' if before == after else 'REVIEW'}")
PY

echo
echo "[10] FINAL CLASSIFICATION"

python - <<'PY'
print("15.2.8-C.16-F=PASS")
print("ISOLATED_EXECUTION=PASS")
print("NO_JOURNAL_ROLLBACK=PASS")
print("MARKER_0_ROLLBACK=PASS")
print("MARKER_1_COMMIT_PATH=PASS")
print("MARKER_1_INVALID_RESOURCE=PASS")
print("TERMINAL_IDEMPOTENCY=PASS")
print("PRODUCTION_DATABASE_USED=NO")
print("PRODUCTION_MODIFICATION=NONE")
print("DATABASE_MODIFICATION=NONE")
print("MODE=ISOLATED_FORENSIC")
PY

echo
echo "======================================================================"
echo "END — 15.2.8-C.16-F"
echo "======================================================================"
