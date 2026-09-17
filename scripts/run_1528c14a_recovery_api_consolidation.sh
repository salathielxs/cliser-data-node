#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
REPORT="$ROOT/tmp/15.2.8-C.14-A-recovery-api-consolidation.txt"
BACKUP="$ROOT/tmp/15.2.8-C.14-A-backup"

mkdir -p "$ROOT/tmp" "$BACKUP"

exec > >(tee "$REPORT") 2>&1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-A"
echo "RECOVERY API CONSOLIDATION"
echo "======================================================================"
echo
echo "MODE=CONTROLLED IMPLEMENTATION"
echo "ROOT=$ROOT"
echo

cd "$ROOT" || exit 1

echo "======================================================================"
echo "[1] PRE-CHANGE SYNTAX"
echo "======================================================================"

python -m py_compile \
    node/transaction.py \
    node/recovery.py

echo "PY_COMPILE=PASS"

echo
echo "======================================================================"
echo "[2] BACKUP"
echo "======================================================================"

cp node/transaction.py "$BACKUP/transaction.py.before"
cp node/recovery.py "$BACKUP/recovery.py.before"

echo "BACKUP_TRANSACTION=$BACKUP/transaction.py.before"
echo "BACKUP_RECOVERY=$BACKUP/recovery.py.before"

echo
echo "======================================================================"
echo "[3] CURRENT RECOVERY API"
echo "======================================================================"

grep -nE \
'^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
node/transaction.py node/recovery.py || true

echo
echo "======================================================================"
echo "[4] CURRENT RECOVERY ENGINE BATCH IMPLEMENTATION"
echo "======================================================================"

sed -n '/^[[:space:]]*def recover_pending_transactions(/,/^[[:space:]]*def recovery_status(/p' \
node/recovery.py

echo
echo "======================================================================"
echo "[5] CREATE CONTRACT TEST"
echo "======================================================================"

cat > /tmp/c14_contract_test.py <<'PY'
from node import recovery

assert callable(recovery.recover_transaction)
assert callable(recovery.recover_pending_transactions)
assert callable(recovery.recovery_status)

print("RECOVERY_PUBLIC_API=PASS")
PY

python /tmp/c14_contract_test.py

echo
echo "======================================================================"
echo "[6] MIGRATION PLAN"
echo "======================================================================"

echo "AUTHORITY=node.recovery"
echo "TRANSACTION_MODEL=node.transaction"
echo "LEGACY_TRANSACTION_RECOVERY=TEMPORARILY_PRESERVED"
echo "STARTUP_RECOVERY=DEFERRED"
echo "RESOURCE_VALIDATION=PRESERVED"
echo "ROLLBACK_CLEANUP=PRESERVED"
echo "IDEMPOTENCY=PRESERVED"
echo "SHARED_BLOCK_PROTECTION=PRESERVED"

echo
echo "======================================================================"
echo "[7] MODIFY RECOVERY ENGINE BATCH CONTRACT"
echo "======================================================================"

python - <<'PY'
from pathlib import Path

path = Path("node/recovery.py")
text = path.read_text()

old = '''def recover_pending_transactions():
    results = []
    transactions = list_transactions()
    for tx in transactions:
        transaction_id = tx[0]
        state = tx[4]
        if state not in RECOVERABLE_STATES:
            continue
        results.append(
            recover_transaction(transaction_id)
        )
    return results
'''

new = '''def recover_pending_transactions():
    """
    Recover all persisted transactions in recoverable states.

    Canonical batch recovery contract.

    Returns:
        dict:
            total: total persisted transactions inspected
            processed: number of recoverable transactions processed
            recovered: number of transactions actually recovered
            noop: number of terminal/no-op results
            errors: number of recovery errors
            results: individual recovery results
    """

    transactions = list_transactions()

    report = {
        "total": len(transactions),
        "processed": 0,
        "recovered": 0,
        "noop": 0,
        "errors": 0,
        "results": [],
    }

    for tx in transactions:
        transaction_id = tx[0]
        state = tx[4]

        if state not in RECOVERABLE_STATES:
            continue

        report["processed"] += 1

        try:
            result = recover_transaction(transaction_id)

            report["results"].append(result)

            if result.get("recovered") is True:
                report["recovered"] += 1
            else:
                report["noop"] += 1

        except Exception as exc:
            report["errors"] += 1
            report["results"].append({
                "transaction_id": transaction_id,
                "action": "ERROR",
                "recovered": False,
                "error": str(exc),
            })

    return report
'''

if old not in text:
    raise SystemExit(
        "ABORT: expected recover_pending_transactions block "
        "was not found exactly; no modification performed."
    )

path.write_text(text.replace(old, new, 1))

print("RECOVERY_BATCH_CONTRACT=UPDATED")
PY

echo
echo "======================================================================"
echo "[8] PYTHON SYNTAX AFTER CHANGE"
echo "======================================================================"

python -m py_compile \
    node/transaction.py \
    node/recovery.py

echo "PY_COMPILE=PASS"

echo
echo "======================================================================"
echo "[9] RECOVERY API CHECK"
echo "======================================================================"

python - <<'PY'
from node import recovery

print("recover_transaction=", callable(recovery.recover_transaction))
print("recover_pending_transactions=", callable(
    recovery.recover_pending_transactions
))
print("recovery_status=", callable(recovery.recovery_status))
PY

echo
echo "======================================================================"
echo "[10] CONTRACT SHAPE CHECK"
echo "======================================================================"

python - <<'PY'
import inspect
from node import recovery

source = inspect.getsource(recovery.recover_pending_transactions)

required = [
    '"total"',
    '"processed"',
    '"recovered"',
    '"noop"',
    '"errors"',
    '"results"',
]

for item in required:
    if item not in source:
        raise SystemExit(
            f"CONTRACT_CHECK_FAILED: missing {item}"
        )

print("BATCH_CONTRACT_FIELDS=PASS")
PY

echo
echo "======================================================================"
echo "[11] RUN TARGETED RECOVERY TESTS"
echo "======================================================================"

pytest -q \
    tests/test_crash_recovery.py \
    tests/test_atomicity.py \
    tests/test_commit_marker.py \
    tests/test_recovery_idempotency.py \
    2>&1

TEST_STATUS=$?

echo
echo "TARGETED_TEST_EXIT=$TEST_STATUS"

echo
echo "======================================================================"
echo "[12] FULL COLLECTION"
echo "======================================================================"

pytest --collect-only -q 2>&1
COLLECT_STATUS=$?

echo
echo "COLLECTION_EXIT=$COLLECT_STATUS"

echo
echo "======================================================================"
echo "[13] GIT DIFF"
echo "======================================================================"

git diff -- node/recovery.py node/transaction.py tests

echo
echo "======================================================================"
echo "[14] GIT STATUS"
echo "======================================================================"

git status --short

echo
echo "======================================================================"
echo "[15] FINAL RESULT"
echo "======================================================================"

if [ "$TEST_STATUS" -eq 0 ] && [ "$COLLECT_STATUS" -eq 0 ]; then
    echo "RESULT=PASS_WITH_COMPATIBILITY_PENDING"
    echo "NEXT=C.14-B"
else
    echo "RESULT=REVIEW"
    echo "NEXT=FORENSIC_FAILURE_ANALYSIS"
fi

echo
echo "15.2.8-C.14-A COMPLETE"
echo "======================================================================"
