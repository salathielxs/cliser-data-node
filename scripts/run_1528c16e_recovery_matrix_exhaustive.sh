#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.16-E"
echo "RECOVERY MATRIX EXHAUSTIVE FORENSIC"
echo "======================================================================"

echo
echo "[1] DEFINIÇÕES DE ESTADO"

python - <<'PY'
from node.transaction import (
    TransactionState,
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

def normalize(value):
    return getattr(value, "value", value)

print("ALL_STATES")
for state in TransactionState:
    print(f"{state.value}")

print()
print("RECOVERABLE")
for state in sorted(normalize(x) for x in RECOVERABLE_STATES):
    print(state)

print()
print("TERMINAL")
for state in sorted(normalize(x) for x in TERMINAL_STATES):
    print(state)
PY

echo
echo "[2] RECOVERY DECISION MATRIX — STATIC"

python - <<'PY'
from node.transaction import (
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

def normalize(value):
    return getattr(value, "value", value)

recoverable = {
    normalize(x) for x in RECOVERABLE_STATES
}

terminal = {
    normalize(x) for x in TERMINAL_STATES
}

states = [
    "PREPARED",
    "WRITING",
    "VERIFYING",
    "COMMITTING",
    "COMMITTED",
    "ROLLBACK",
    "FAILED",
]

print()
print("STATE | JOURNAL | MARKER | EXPECTED_DECISION")
print("------------------------------------------------------------")

for state in states:

    if state in terminal:
        print(f"{state} | ANY | ANY | NOOP")
        continue

    if state not in recoverable:
        print(f"{state} | ANY | ANY | NOOP_UNSUPPORTED_STATE")
        continue

    print(f"{state} | ABSENT | 0 | ROLLBACK")
    print(f"{state} | ABSENT | 1 | ROLLBACK")
    print(f"{state} | PRESENT | 0 | ROLLBACK")
    print(f"{state} | PRESENT | 1 | COMMIT_OR_ROLLBACK_RESOURCE_VALIDATION")

print()
print("MATRIX_ROWS_GENERATED=PASS")
PY

echo
echo "[3] RECOVERY ENGINE CONTRACT EXTRACTION"

python - <<'PY'
import inspect
import node.recovery as recovery

source = inspect.getsource(recovery.recover_transaction)

required_fragments = {
    "TERMINAL_COMMITTED_NOOP":
        'previous_state in {"COMMITTED", "ROLLBACK"}',

    "JOURNAL_LOOKUP":
        "get_transaction_journal(transaction_id)",

    "MARKER_EXTRACTION":
        'journal.get("commit_marker", False)',

    "MISSING_JOURNAL_ROLLBACK":
        'if journal is None:',

    "MISSING_MARKER_ROLLBACK":
        'if not commit_marker:',

    "MARKER_COMMIT_ATTEMPT":
        "_recover_commit(",

    "FAILED_COMMIT_ROLLBACK":
        "_rollback_transaction(",

    "UNSUPPORTED_STATE":
        "NOOP_UNSUPPORTED_STATE",
}

for name, fragment in required_fragments.items():
    print(
        f"{name}=" +
        ("PASS" if fragment in source else "FAIL")
    )
PY

echo
echo "[4] COMMIT RECOVERY RESOURCE VALIDATION"

sed -n '175,230p' node/recovery.py

echo
echo "[5] ROLLBACK CLEANUP SEMANTICS"

sed -n '231,259p' node/recovery.py

echo
echo "[6] EXHAUSTIVE STATE CLASSIFICATION"

python - <<'PY'
from node.transaction import (
    TransactionState,
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

def normalize(value):
    return getattr(value, "value", value)

recoverable = {
    normalize(x) for x in RECOVERABLE_STATES
}

terminal = {
    normalize(x) for x in TERMINAL_STATES
}

expected_recoverable = {
    "PREPARED",
    "WRITING",
    "VERIFYING",
    "COMMITTING",
}

expected_terminal = {
    "COMMITTED",
    "ROLLBACK",
}

all_states = {
    state.value for state in TransactionState
}

print(
    "RECOVERABLE_COMPLETE=" +
    ("PASS" if recoverable == expected_recoverable else "FAIL")
)

print(
    "TERMINAL_COMPLETE=" +
    ("PASS" if terminal == expected_terminal else "FAIL")
)

print(
    "FAILED_NOT_RECOVERABLE=" +
    ("PASS" if "FAILED" not in recoverable else "FAIL")
)

print(
    "STATE_PARTITION_SAFE=" +
    (
        "PASS"
        if recoverable.isdisjoint(terminal)
        and recoverable | terminal | {"FAILED"} == all_states
        else "FAIL"
    )
)

print()
print("STATE_COUNT")
print(f"ALL={len(all_states)}")
print(f"RECOVERABLE={len(recoverable)}")
print(f"TERMINAL={len(terminal)}")
print("FAILED=1")
PY

echo
echo "[7] IDEMPOTENCY CONTRACT"

python - <<'PY'
import inspect
import node.recovery as recovery

source = inspect.getsource(recovery.recover_transaction)

checks = {
    "TERMINAL_NOOP":
        'action": "NOOP"' in source,

    "COMMIT_FINAL_STATE":
        '"final_state": "COMMITTED"' in source,

    "ROLLBACK_FINAL_STATE":
        '"final_state": "ROLLBACK"' in source,

    "RECOVERED_FLAG":
        '"recovered": True' in source,

    "COMMIT_MARKER_RETURN":
        '"commit_marker": True' in source,

    "ROLLBACK_MARKER_RETURN":
        '"commit_marker": False' in source,
}

for name, ok in checks.items():
    print(f"{name}={'PASS' if ok else 'FAIL'}")
PY

echo
echo "[8] GLOBAL RECOVERY SELECTION"

python - <<'PY'
import inspect
import node.recovery as recovery

source = inspect.getsource(
    recovery.recover_pending_transactions
)

checks = {
    "LIST_TRANSACTIONS":
        "list_transactions()" in source,

    "RECOVERABLE_FILTER":
        "row[4] in RECOVERABLE_STATES" in source,

    "PER_TRANSACTION_RECOVERY":
        "recover_transaction(" in source,

    "ERROR_ACCOUNTING":
        '"errors"' in source,

    "RESULT_REPORT":
        '"results"' in source,
}

for name, ok in checks.items():
    print(f"{name}={'PASS' if ok else 'FAIL'}")
PY

echo
echo "[9] CURRENT DATABASE — READ ONLY"

python - <<'PY'
from node.registry import list_transactions
from node.transaction import RECOVERABLE_STATES

def normalize(value):
    return getattr(value, "value", value)

recoverable = {
    normalize(x) for x in RECOVERABLE_STATES
}

rows = list_transactions()

counts = {}

for row in rows:
    state = row[4]
    counts[state] = counts.get(state, 0) + 1

print(f"TOTAL_TRANSACTIONS={len(rows)}")

for state in sorted(counts):
    print(
        f"STATE={state} COUNT={counts[state]}"
    )

pending = [
    row for row in rows
    if row[4] in recoverable
]

print()
print(
    f"RECOVERY_CANDIDATES={len(pending)}"
)
PY

echo
echo "[10] PYTHON COMPILE"

python -m py_compile \
    node/transaction.py \
    node/recovery.py \
    node/registry.py \
    node/object_manager.py \
    api/app.py

echo "PY_COMPILE_RC=$?"

echo
echo "[11] FINAL FORENSIC CLASSIFICATION"

python - <<'PY'
from node.transaction import (
    TransactionState,
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

def normalize(value):
    return getattr(value, "value", value)

all_states = {
    state.value for state in TransactionState
}

recoverable = {
    normalize(x) for x in RECOVERABLE_STATES
}

terminal = {
    normalize(x) for x in TERMINAL_STATES
}

expected_recoverable = {
    "PREPARED",
    "WRITING",
    "VERIFYING",
    "COMMITTING",
}

expected_terminal = {
    "COMMITTED",
    "ROLLBACK",
}

checks = [
    recoverable == expected_recoverable,
    terminal == expected_terminal,
    recoverable.isdisjoint(terminal),
    "FAILED" in all_states,
    "FAILED" not in recoverable,
    "FAILED" not in terminal,
]

print(
    "15.2.8-C.16-E=" +
    ("PASS" if all(checks) else "REVIEW")
)

print(
    "RECOVERY_MATRIX=COMPLETE"
    if all(checks)
    else "RECOVERY_MATRIX=INCOMPLETE"
)

print("MODE=READ_ONLY")
print("PRODUCTION_MODIFICATION=NONE")
print("DATABASE_MODIFICATION=NONE")
PY

echo
echo "======================================================================"
echo "END — 15.2.8-C.16-E"
echo "======================================================================"
