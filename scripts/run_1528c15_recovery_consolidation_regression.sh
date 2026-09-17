#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.15 — RECOVERY CONSOLIDATION REGRESSION GATE"
echo "======================================================================"

RC_COMPILE=0
RC_TRANSACTION=0
RC_RECOVERY=0
RC_COMMIT=0
RC_ATOMICITY=0
RC_CRASH=0
RC_IDEMPOTENCY=0
RC_OBJECT_ID=0

echo
echo "[1] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
    node/transaction.py \
    node/recovery.py \
    node/object_manager.py \
    node/registry.py

RC_COMPILE=$?

echo "PY_COMPILE_RC=$RC_COMPILE"

echo
echo "[2] TRANSACTION MODEL"
echo "----------------------------------------------------------------------"

python - <<'PY'
from node.transaction import (
    Transaction,
    TransactionState,
    VALID_TRANSITIONS,
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

required_states = {
    "PREPARED",
    "WRITING",
    "VERIFYING",
    "COMMITTING",
    "COMMITTED",
    "FAILED",
    "ROLLBACK",
}

actual_states = {
    state.value
    for state in TransactionState
}

print("REQUIRED_STATES_PRESENT=" + str(
    required_states.issubset(actual_states)
))

print("RECOVERABLE_STATES=" + ",".join(
    sorted(state.value for state in RECOVERABLE_STATES)
))

print("TERMINAL_STATES=" + ",".join(
    sorted(state.value for state in TERMINAL_STATES)
))

print("TRANSACTION_CLASS=" + str(Transaction is not None))
print("ROLLBACK_METHOD=" + str(hasattr(Transaction, "rollback")))

if (
    required_states.issubset(actual_states)
    and hasattr(Transaction, "rollback")
    and RECOVERABLE_STATES
    and TERMINAL_STATES
):
    print("TRANSACTION_MODEL=PASS")
else:
    print("TRANSACTION_MODEL=FAIL")
    raise SystemExit(1)
PY

RC_TRANSACTION=$?

echo "TRANSACTION_RC=$RC_TRANSACTION"

echo
echo "[3] RECOVERY ENGINE"
echo "----------------------------------------------------------------------"

python - <<'PY'
import node.recovery as recovery

required = [
    "recover_transaction",
    "recover_pending_transactions",
    "recovery_status",
    "_recover_commit",
    "_rollback_transaction",
]

missing = [
    name
    for name in required
    if not hasattr(recovery, name)
]

print("REQUIRED_RECOVERY_FUNCTIONS=" + str(len(required)))
print("MISSING_RECOVERY_FUNCTIONS=" + str(missing))

if missing:
    print("RECOVERY_ENGINE=FAIL")
    raise SystemExit(1)

print("RECOVERY_ENGINE=PASS")
PY

RC_RECOVERY=$?

echo "RECOVERY_RC=$RC_RECOVERY"

echo
echo "[4] COMMIT MARKER"
echo "----------------------------------------------------------------------"

PYTHONPATH="$ROOT" python -m pytest -q \
    tests/test_commit_marker.py

RC_COMMIT=$?

echo "COMMIT_MARKER_RC=$RC_COMMIT"

echo
echo "[5] ATOMICITY"
echo "----------------------------------------------------------------------"

PYTHONPATH="$ROOT" python -m pytest -q \
    tests/test_atomicity.py

RC_ATOMICITY=$?

echo "ATOMICITY_RC=$RC_ATOMICITY"

echo
echo "[6] CRASH RECOVERY"
echo "----------------------------------------------------------------------"

PYTHONPATH="$ROOT" python -m pytest -q \
    tests/test_crash_recovery.py

RC_CRASH=$?

echo "CRASH_RECOVERY_RC=$RC_CRASH"

echo
echo "[7] RECOVERY IDEMPOTENCY"
echo "----------------------------------------------------------------------"

PYTHONPATH="$ROOT" python -m pytest -q \
    tests/test_recovery_idempotency.py

RC_IDEMPOTENCY=$?

echo "RECOVERY_IDEMPOTENCY_RC=$RC_IDEMPOTENCY"

echo
echo "[8] OBJECT IDENTITY CONTRACT"
echo "----------------------------------------------------------------------"

python - <<'PY'
from pathlib import Path

source = Path("node/object_manager.py").read_text()

checks = {
    "UUID_OBJECT_ID": "object_id = uuid.uuid4().hex" in source,
    "SHA256_CONTENT_HASH": (
        "content_hash = hashlib.sha256(data).hexdigest()"
        in source
    ),
    "UUID_NOT_CONTENT_HASH": (
        "object_id = content_hash"
        not in source
    ),
}

for name, result in checks.items():
    print(f"{name}={result}")

if all(checks.values()):
    print("OBJECT_IDENTITY_CONTRACT=PASS")
else:
    print("OBJECT_IDENTITY_CONTRACT=FAIL")
    raise SystemExit(1)
PY

RC_OBJECT_ID=$?

echo "OBJECT_IDENTITY_RC=$RC_OBJECT_ID"

echo
echo "[9] FINAL"
echo "----------------------------------------------------------------------"

if [ "$RC_COMPILE" -eq 0 ] &&
   [ "$RC_TRANSACTION" -eq 0 ] &&
   [ "$RC_RECOVERY" -eq 0 ] &&
   [ "$RC_COMMIT" -eq 0 ] &&
   [ "$RC_ATOMICITY" -eq 0 ] &&
   [ "$RC_CRASH" -eq 0 ] &&
   [ "$RC_IDEMPOTENCY" -eq 0 ] &&
   [ "$RC_OBJECT_ID" -eq 0 ]; then

    echo "15.2.8-C.15=PASS"
    echo "COMPILE=PASS"
    echo "TRANSACTION_MODEL=PASS"
    echo "RECOVERY_ENGINE=PASS"
    echo "COMMIT_MARKER=PASS"
    echo "ATOMICITY=PASS"
    echo "CRASH_RECOVERY=PASS"
    echo "RECOVERY_IDEMPOTENCY=PASS"
    echo "OBJECT_IDENTITY=PASS"

else

    echo "15.2.8-C.15=REVIEW"
    echo "COMPILE_RC=$RC_COMPILE"
    echo "TRANSACTION_RC=$RC_TRANSACTION"
    echo "RECOVERY_RC=$RC_RECOVERY"
    echo "COMMIT_RC=$RC_COMMIT"
    echo "ATOMICITY_RC=$RC_ATOMICITY"
    echo "CRASH_RC=$RC_CRASH"
    echo "IDEMPOTENCY_RC=$RC_IDEMPOTENCY"
    echo "OBJECT_IDENTITY_RC=$RC_OBJECT_ID"
fi

echo
echo "======================================================================"
echo "15.2.8-C.15 — COMPLETE"
echo "======================================================================"
