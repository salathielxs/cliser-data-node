#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.16-D"
echo "RESTART RECOVERY SEMANTICS FORENSIC"
echo "======================================================================"

echo
echo "[1] TRANSACTION STATES / RECOVERY SETS"
python - <<'PY'
from node.transaction import (
    TransactionState,
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

def normalize(value):
    return getattr(value, "value", value)

print("TRANSACTION_STATES")
for state in TransactionState:
    print(f"  {state.name}={state.value}")

print()
print("RECOVERABLE_STATES")
for state in sorted(normalize(x) for x in RECOVERABLE_STATES):
    print(f"  {state}")

print()
print("TERMINAL_STATES")
for state in sorted(normalize(x) for x in TERMINAL_STATES):
    print(f"  {state}")

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

actual_recoverable = {
    normalize(x) for x in RECOVERABLE_STATES
}

actual_terminal = {
    normalize(x) for x in TERMINAL_STATES
}

print()
print(
    "RECOVERABLE_SET_CONTRACT=" +
    ("PASS" if actual_recoverable == expected_recoverable else "FAIL")
)

print(
    "TERMINAL_SET_CONTRACT=" +
    ("PASS" if actual_terminal == expected_terminal else "FAIL")
)
PY

echo
echo "[2] RECOVERY ENGINE BRANCHES"
grep -nE \
  'def recover_transaction|def recover_pending_transactions|COMMITTED|ROLLBACK|NOOP|NOT_FOUND|NOOP_UNSUPPORTED_STATE|_recover_commit|_rollback_transaction|commit_marker|journal' \
  node/recovery.py

echo
echo "[3] RECOVER_TRANSACTION IMPLEMENTATION"
sed -n '240,387p' node/recovery.py

echo
echo "[4] GLOBAL RECOVERY IMPLEMENTATION"
sed -n '388,466p' node/recovery.py

echo
echo "[5] COMMIT RECOVERY IMPLEMENTATION"
grep -nE \
  '^def _recover_commit|^def _rollback_transaction|^def recover_transaction|^def recover_pending_transactions' \
  node/recovery.py

echo
echo "[6] JOURNAL / COMMIT MARKER SEMANTICS"
python - <<'PY'
import inspect
import node.recovery as recovery

print("recover_transaction signature:")
print(inspect.signature(recovery.recover_transaction))

print()
print("recover_pending_transactions signature:")
print(inspect.signature(recovery.recover_pending_transactions))

print()
print("_recover_commit signature:")
print(inspect.signature(recovery._recover_commit))

print()
print("_rollback_transaction signature:")
print(inspect.signature(recovery._rollback_transaction))
PY

echo
echo "[7] TERMINAL STATE BEHAVIOR — STATIC CHECK"
python - <<'PY'
from node.recovery import recover_transaction
import inspect

source = inspect.getsource(recover_transaction)

checks = {
    "COMMITTED_NOOP": "COMMITTED" in source and "NOOP" in source,
    "ROLLBACK_NOOP": "ROLLBACK" in source and "NOOP" in source,
    "MISSING_JOURNAL_ROLLBACK": "journal" in source,
    "MISSING_COMMIT_MARKER_ROLLBACK": "commit_marker" in source,
    "COMMIT_RECOVERY": "_recover_commit" in source,
    "ROLLBACK_ENGINE": "_rollback_transaction" in source,
    "UNSUPPORTED_STATE": "NOOP_UNSUPPORTED_STATE" in source,
}

for name, result in checks.items():
    print(f"{name}={'PASS' if result else 'FAIL'}")
PY

echo
echo "[8] RECOVERY ENGINE COMPILE"
python -m py_compile \
  node/transaction.py \
  node/recovery.py \
  node/registry.py \
  node/object_manager.py \
  api/app.py

echo "PY_COMPILE_RC=$?"

echo
echo "[9] PERSISTED STATE SNAPSHOT — READ ONLY"
python - <<'PY'
from node.registry import list_transactions
from node.transaction import RECOVERABLE_STATES

def normalize(value):
    return getattr(value, "value", value)

recoverable = {normalize(x) for x in RECOVERABLE_STATES}

rows = list_transactions()

counts = {}

for row in rows:
    state = row[4]
    counts[state] = counts.get(state, 0) + 1

print(f"TOTAL_TRANSACTIONS={len(rows)}")

for state in sorted(counts):
    print(f"STATE={state} COUNT={counts[state]}")

pending = [
    row for row in rows
    if row[4] in recoverable
]

print()
print(f"PERSISTED_RECOVERY_CANDIDATES={len(pending)}")

for row in pending:
    print(
        "CANDIDATE",
        f"transaction_id={row[0]}",
        f"object_id={row[1]}",
        f"namespace={row[2]}",
        f"operation={row[3]}",
        f"state={row[4]}",
    )
PY

echo
echo "[10] RECOVERY SELECTION DETERMINISM"
python - <<'PY'
from node.registry import list_transactions
from node.transaction import RECOVERABLE_STATES

def normalize(value):
    return getattr(value, "value", value)

recoverable = {normalize(x) for x in RECOVERABLE_STATES}

rows_a = list_transactions()
rows_b = list_transactions()

candidates_a = [
    row[0]
    for row in rows_a
    if row[4] in recoverable
]

candidates_b = [
    row[0]
    for row in rows_b
    if row[4] in recoverable
]

print(f"FIRST_SCAN={len(candidates_a)}")
print(f"SECOND_SCAN={len(candidates_b)}")
print(
    "SELECTION_STABLE=" +
    ("PASS" if candidates_a == candidates_b else "FAIL")
)
PY

echo
echo "[11] FINAL FORENSIC CLASSIFICATION"

python - <<'PY'
from node.transaction import (
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

def normalize(value):
    return getattr(value, "value", value)

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

recoverable_ok = {
    normalize(x) for x in RECOVERABLE_STATES
} == expected_recoverable

terminal_ok = {
    normalize(x) for x in TERMINAL_STATES
} == expected_terminal

print(
    "15.2.8-C.16-D=" +
    ("PASS" if recoverable_ok and terminal_ok else "REVIEW")
)

print(
    "RESTART_DECISION_SOURCE=transactions.state"
)

print(
    "RECOVERABLE_STATES=" +
    ("DETERMINISTIC" if recoverable_ok else "INVALID")
)

print(
    "TERMINAL_STATES=" +
    ("DETERMINISTIC" if terminal_ok else "INVALID")
)

print(
    "MODE=READ_ONLY"
)

print(
    "PRODUCTION_MODIFICATION=NONE"
)

print(
    "DATABASE_MODIFICATION=NONE"
)
PY

echo
echo "======================================================================"
echo "END — 15.2.8-C.16-D"
echo "======================================================================"
