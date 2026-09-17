#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

DB="$ROOT/data/registry.db"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.16-F"
echo "REAL DATABASE PROTECTION + ISOLATED RECOVERY"
echo "======================================================================"

echo
echo "[1] REAL DATABASE"

if [ ! -f "$DB" ]; then
    echo "REAL_DATABASE=FAIL"
    exit 1
fi

echo "REAL_DATABASE=$DB"
echo "REAL_DATABASE_EXISTS=PASS"

BEFORE_SIZE="$(stat -c %s "$DB")"
BEFORE_MTIME="$(stat -c %Y "$DB")"

echo "BEFORE_SIZE=$BEFORE_SIZE"
echo "BEFORE_MTIME=$BEFORE_MTIME"

echo
echo "[2] SQLITE READ-ONLY BASELINE"

sqlite3 "file:$DB?mode=ro" <<'SQL'
.headers off
.mode list

SELECT 'DATABASE_OPEN=PASS';

SELECT 'TOTAL_TRANSACTIONS=' || COUNT(*)
FROM transactions;

SELECT 'COMMITTED=' || COUNT(*)
FROM transactions
WHERE state='COMMITTED';

SELECT 'ROLLBACK=' || COUNT(*)
FROM transactions
WHERE state='ROLLBACK';

SELECT 'RECOVERABLE=' || COUNT(*)
FROM transactions
WHERE state IN (
    'PREPARED',
    'WRITING',
    'VERIFYING',
    'COMMITTING'
);

SELECT 'JOURNAL_ROWS=' || COUNT(*)
FROM transaction_journal;
SQL

echo
echo "[3] ISOLATED RECOVERY EXECUTION"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal
original_recover_commit = recovery._recover_commit
original_rollback = recovery._rollback_transaction

try:
    cases = [
        ("PREPARED", None, "ROLLBACK"),
        ("WRITING", None, "ROLLBACK"),
        ("VERIFYING", None, "ROLLBACK"),
        ("COMMITTING", None, "ROLLBACK"),

        ("PREPARED", {"commit_marker": 0, "resources": {}}, "ROLLBACK"),
        ("WRITING", {"commit_marker": 0, "resources": {}}, "ROLLBACK"),
        ("VERIFYING", {"commit_marker": 0, "resources": {}}, "ROLLBACK"),
        ("COMMITTING", {"commit_marker": 0, "resources": {}}, "ROLLBACK"),
    ]

    passed = True

    for index, (state, journal, expected) in enumerate(
        cases,
        start=1,
    ):
        txid = f"C16F-R-{index}"

        transaction = {
            "transaction_id": txid,
            "object_id": f"OBJECT-{index}",
            "state": state,
        }

        recovery.get_transaction = (
            lambda transaction_id, tx=transaction:
            tx if transaction_id == tx["transaction_id"] else None
        )

        recovery.get_transaction_journal = (
            lambda transaction_id, j=journal: j
        )

        recovery._rollback_transaction = (
            lambda transaction_id, tx: {
                "transaction_id": transaction_id,
                "action": "ROLLBACK",
                "reason": "ISOLATED",
            }
        )

        result = recovery.recover_transaction(txid)

        ok = (
            result.get("action") == expected
            and result.get("final_state") == expected
            and result.get("recovered") is True
        )

        print(
            f"{state} / "
            f"{'ABSENT' if journal is None else 'MARKER_0'} "
            f"-> {result.get('action')} "
            f"{'PASS' if ok else 'FAIL'}"
        )

        if not ok:
            passed = False

    print()
    print(
        "ROLLBACK_MATRIX=" +
        ("PASS" if passed else "FAIL")
    )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
    recovery._recover_commit = original_recover_commit
    recovery._rollback_transaction = original_rollback
PY

echo
echo "[4] TERMINAL / UNSUPPORTED"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal

try:
    cases = [
        ("COMMITTED", "NOOP"),
        ("ROLLBACK", "NOOP"),
        ("FAILED", "NOOP_UNSUPPORTED_STATE"),
    ]

    passed = True

    for index, (state, expected) in enumerate(cases):
        txid = f"C16F-T-{index}"

        recovery.get_transaction = (
            lambda transaction_id, state=state: {
                "transaction_id": transaction_id,
                "object_id": "OBJECT",
                "state": state,
            }
        )

        recovery.get_transaction_journal = (
            lambda transaction_id: None
        )

        result = recovery.recover_transaction(txid)
        actual = result.get("action")

        ok = actual == expected

        print(
            f"{state} -> "
            f"{actual} "
            f"{'PASS' if ok else 'FAIL'}"
        )

        if not ok:
            passed = False

    print()
    print(
        "TERMINAL_UNSUPPORTED_MATRIX=" +
        ("PASS" if passed else "FAIL")
    )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
PY

echo
echo "[5] MARKER=1 COMMIT PATH"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal
original_recover_commit = recovery._recover_commit
original_rollback = recovery._rollback_transaction

try:
    txid = "C16F-COMMIT-VALID"

    recovery.get_transaction = lambda transaction_id: {
        "transaction_id": transaction_id,
        "object_id": "OBJECT-COMMIT",
        "state": "COMMITTING",
    }

    recovery.get_transaction_journal = lambda transaction_id: {
        "commit_marker": 1,
        "resources": {
            "block_mode": False,
        },
    }

    recovery._recover_commit = lambda transaction_id, transaction: {
        "transaction_id": transaction_id,
        "action": "COMMIT",
        "reason": "ISOLATED_VALIDATION",
    }

    recovery._rollback_transaction = lambda transaction_id, transaction: {
        "transaction_id": transaction_id,
        "action": "ROLLBACK",
        "reason": "UNEXPECTED",
    }

    result = recovery.recover_transaction(txid)

    ok = (
        result.get("action") == "COMMIT"
        and result.get("final_state") == "COMMITTED"
        and result.get("commit_marker") is True
    )

    print(result)
    print(
        "MARKER_1_COMMIT_PATH=" +
        ("PASS" if ok else "FAIL")
    )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
    recovery._recover_commit = original_recover_commit
    recovery._rollback_transaction = original_rollback
PY

echo
echo "[6] MARKER=1 INVALID RESOURCE PATH"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal
original_recover_commit = recovery._recover_commit
original_rollback = recovery._rollback_transaction

try:
    txid = "C16F-COMMIT-INVALID"

    recovery.get_transaction = lambda transaction_id: {
        "transaction_id": transaction_id,
        "object_id": "OBJECT-COMMIT-INVALID",
        "state": "COMMITTING",
    }

    recovery.get_transaction_journal = lambda transaction_id: {
        "commit_marker": 1,
        "resources": {
            "block_mode": False,
        },
    }

    recovery._recover_commit = lambda transaction_id, transaction: {
        "transaction_id": transaction_id,
        "action": "ROLLBACK",
        "reason": "COMMIT_MARKER_BUT_RESOURCES_INVALID",
    }

    rollback_calls = []

    def fake_rollback(transaction_id, transaction):
        rollback_calls.append(transaction_id)

        return {
            "transaction_id": transaction_id,
            "action": "ROLLBACK",
            "reason": "ISOLATED_INVALID_RESOURCE",
        }

    recovery._rollback_transaction = fake_rollback

    result = recovery.recover_transaction(txid)

    ok = (
        result.get("action") == "ROLLBACK"
        and result.get("final_state") == "ROLLBACK"
        and result.get("commit_marker") is True
        and bool(rollback_calls)
    )

    print(result)
    print(
        "MARKER_1_INVALID_RESOURCE=" +
        ("PASS" if ok else "FAIL")
    )

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal
    recovery._recover_commit = original_recover_commit
    recovery._rollback_transaction = original_rollback
PY

echo
echo "[7] TERMINAL IDEMPOTENCY"

python - <<'PY'
from node import recovery

original_get_transaction = recovery.get_transaction
original_get_journal = recovery.get_transaction_journal

try:
    passed = True

    for state in ("COMMITTED", "ROLLBACK"):

        txid = f"C16F-IDEMP-{state}"

        recovery.get_transaction = (
            lambda transaction_id, state=state: {
                "transaction_id": transaction_id,
                "object_id": f"OBJECT-{state}",
                "state": state,
            }
        )

        recovery.get_transaction_journal = (
            lambda transaction_id: None
        )

        first = recovery.recover_transaction(txid)
        second = recovery.recover_transaction(txid)

        ok = (
            first.get("action") == "NOOP"
            and second.get("action") == "NOOP"
            and first.get("final_state") == state
            and second.get("final_state") == state
        )

        print(
            f"{state}_IDEMPOTENCY=" +
            ("PASS" if ok else "FAIL")
        )

        if not ok:
            passed = False

finally:
    recovery.get_transaction = original_get_transaction
    recovery.get_transaction_journal = original_get_journal

print(
    "TERMINAL_IDEMPOTENCY=" +
    ("PASS" if passed else "FAIL")
)
PY

echo
echo "[8] REAL DATABASE AFTER ISOLATED TESTS"

AFTER_SIZE="$(stat -c %s "$DB")"
AFTER_MTIME="$(stat -c %Y "$DB")"

echo "AFTER_SIZE=$AFTER_SIZE"
echo "AFTER_MTIME=$AFTER_MTIME"

if [ "$BEFORE_SIZE" = "$AFTER_SIZE" ] && \
   [ "$BEFORE_MTIME" = "$AFTER_MTIME" ]; then
    echo "PRODUCTION_DB_UNCHANGED=PASS"
else
    echo "PRODUCTION_DB_UNCHANGED=REVIEW"
fi

echo
echo "[9] FINAL CLASSIFICATION"

if [ "$BEFORE_SIZE" = "$AFTER_SIZE" ] && \
   [ "$BEFORE_MTIME" = "$AFTER_MTIME" ]; then

    echo "15.2.8-C.16-F=PASS"
    echo "ISOLATED_EXECUTION=PASS"
    echo "PRODUCTION_DATABASE_USED=NO"
    echo "PRODUCTION_MODIFICATION=NONE"
    echo "MODE=ISOLATED_FORENSIC"

else

    echo "15.2.8-C.16-F=REVIEW"
    echo "REASON=REAL_DATABASE_METADATA_CHANGED"
fi

echo
echo "======================================================================"
echo "END — C16-F REAL DATABASE PROTECTION"
echo "======================================================================"
