#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.16-C"
echo "RECOVERY SOURCE OF TRUTH FORENSIC"
echo "======================================================================"

echo
echo "[1] TRANSACTION SCHEMA"
echo "----------------------------------------------------------------------"

python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/registry.db")

print(f"DB={db}")
print(f"EXISTS={db.exists()}")

if not db.exists():
    raise SystemExit(0)

uri = f"file:{db.resolve()}?mode=ro"
conn = sqlite3.connect(uri, uri=True)

for table in ("transactions", "transaction_journal"):
    print()
    print(f"TABLE={table}")

    rows = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    if not rows:
        print("TABLE_NOT_FOUND")
        continue

    for row in rows:
        print(
            f"column={row[1]} "
            f"type={row[2]} "
            f"notnull={row[3]} "
            f"default={row[4]} "
            f"pk={row[5]}"
        )

conn.close()
PY

echo
echo "[2] PERSISTED TRANSACTION STATES"
echo "----------------------------------------------------------------------"

python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/registry.db")

if not db.exists():
    print("DB_NOT_FOUND")
    raise SystemExit(0)

uri = f"file:{db.resolve()}?mode=ro"
conn = sqlite3.connect(uri, uri=True)

try:
    total = conn.execute(
        "SELECT COUNT(*) FROM transactions"
    ).fetchone()[0]

    print(f"TOTAL_TRANSACTIONS={total}")

    rows = conn.execute(
        """
        SELECT state, COUNT(*)
        FROM transactions
        GROUP BY state
        ORDER BY state
        """
    ).fetchall()

    for state, count in rows:
        print(f"STATE={state} COUNT={count}")

finally:
    conn.close()
PY

echo
echo "[3] RECOVERY STATE MODEL"
echo "----------------------------------------------------------------------"

python - <<'PY'
from node.transaction import (
    TransactionState,
    RECOVERABLE_STATES,
    TERMINAL_STATES,
)

print("TRANSACTION_STATES=")
for state in TransactionState:
    print(f"  {state.name}={state.value}")

print()
print("RECOVERABLE_STATES=")
for state in sorted(RECOVERABLE_STATES, key=str):
    value = getattr(state, "value", state)
    print(f"  {value}")

print()
print("TERMINAL_STATES=")
for state in sorted(TERMINAL_STATES, key=str):
    value = getattr(state, "value", state)
    print(f"  {value}")
PY

echo
echo "[4] list_transactions() IMPLEMENTATION"
echo "----------------------------------------------------------------------"

grep -n -A45 -B5 \
    "def list_transactions" \
    node/registry.py || true

echo
echo "[5] recover_pending_transactions() IMPLEMENTATION"
echo "----------------------------------------------------------------------"

grep -n -A100 -B10 \
    "def recover_pending_transactions" \
    node/recovery.py || true

echo
echo "[6] RECOVERY CANDIDATE SELECTION"
echo "----------------------------------------------------------------------"

python - <<'PY'
import sqlite3
from pathlib import Path

from node.transaction import RECOVERABLE_STATES

db = Path("data/registry.db")

if not db.exists():
    print("DB_NOT_FOUND")
    raise SystemExit(0)

recoverable = {
    getattr(state, "value", state)
    for state in RECOVERABLE_STATES
}

print(
    "RECOVERABLE_STATE_SET="
    + ",".join(sorted(recoverable))
)

uri = f"file:{db.resolve()}?mode=ro"
conn = sqlite3.connect(uri, uri=True)

try:
    placeholders = ",".join("?" for _ in recoverable)

    rows = conn.execute(
        f"""
        SELECT transaction_id, state
        FROM transactions
        WHERE state IN ({placeholders})
        ORDER BY transaction_id
        """,
        tuple(sorted(recoverable)),
    ).fetchall()

    print(f"PERSISTED_RECOVERY_CANDIDATES={len(rows)}")

    for transaction_id, state in rows:
        print(
            f"CANDIDATE transaction_id={transaction_id} state={state}"
        )

finally:
    conn.close()
PY

echo
echo "[7] JOURNAL / COMMIT MARKER CORRELATION"
echo "----------------------------------------------------------------------"

python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/registry.db")

if not db.exists():
    print("DB_NOT_FOUND")
    raise SystemExit(0)

uri = f"file:{db.resolve()}?mode=ro"
conn = sqlite3.connect(uri, uri=True)

try:
    print("JOURNAL_ROWS_BY_COMMIT_MARKER")

    rows = conn.execute(
        """
        SELECT
            CASE
                WHEN commit_marker IS NULL THEN 'NULL'
                WHEN commit_marker = 0 THEN 'FALSE_0'
                WHEN commit_marker = 1 THEN 'TRUE_1'
                ELSE 'OTHER'
            END AS marker_state,
            COUNT(*)
        FROM transaction_journal
        GROUP BY marker_state
        ORDER BY marker_state
        """
    ).fetchall()

    for marker_state, count in rows:
        print(
            f"COMMIT_MARKER={marker_state} COUNT={count}"
        )

    print()
    print("RECOVERY_CANDIDATES_WITH_JOURNAL")

    rows = conn.execute(
        """
        SELECT
            t.transaction_id,
            t.state,
            CASE
                WHEN j.transaction_id IS NULL THEN 'ABSENT'
                ELSE 'PRESENT'
            END AS journal,
            CASE
                WHEN j.transaction_id IS NULL THEN 'N/A'
                WHEN j.commit_marker IS NULL THEN 'NULL'
                WHEN j.commit_marker = 0 THEN 'FALSE_0'
                WHEN j.commit_marker = 1 THEN 'TRUE_1'
                ELSE 'OTHER'
            END AS commit_marker
        FROM transactions t
        LEFT JOIN transaction_journal j
            ON j.transaction_id = t.transaction_id
        WHERE t.state IN (
            'PREPARED',
            'WRITING',
            'VERIFYING',
            'COMMITTING'
        )
        ORDER BY t.transaction_id
        """
    ).fetchall()

    print(f"ROWS={len(rows)}")

    for row in rows:
        print(
            "transaction_id=%s state=%s journal=%s commit_marker=%s"
            % row
        )

finally:
    conn.close()
PY

echo
echo "[8] RECOVERY ENGINE CONTRACT"
echo "----------------------------------------------------------------------"

grep -n -A180 -B15 \
    "def recover_transaction" \
    node/recovery.py || true

echo
echo "[9] RECOVERY ENTRYPOINTS"
echo "----------------------------------------------------------------------"

grep -nE \
    '^(def|async def) (recover_transaction|recover_pending_transactions|recovery_status)\(' \
    node/recovery.py || true

echo
echo "[10] EXTERNAL RECOVERY REFERENCES"
echo "----------------------------------------------------------------------"

grep -RniE \
    'recover_pending_transactions|recover_transaction|recovery_status' \
    api node tests scripts \
    --exclude='recovery.py' \
    --exclude-dir='__pycache__' \
    2>/dev/null || true

echo
echo "[11] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
    node/transaction.py \
    node/recovery.py \
    node/registry.py \
    api/app.py

PY_COMPILE_RC=$?

echo "PY_COMPILE_RC=$PY_COMPILE_RC"

echo
echo "[12] READ-ONLY DATABASE CONFIRMATION"
echo "----------------------------------------------------------------------"

python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/registry.db")

if not db.exists():
    print("DB_NOT_FOUND")
    raise SystemExit(0)

uri = f"file:{db.resolve()}?mode=ro"
conn = sqlite3.connect(uri, uri=True)

print("SQLITE_READ_ONLY_OPEN=PASS")

try:
    journal_count = conn.execute(
        "SELECT COUNT(*) FROM transaction_journal"
    ).fetchone()[0]

    transaction_count = conn.execute(
        "SELECT COUNT(*) FROM transactions"
    ).fetchone()[0]

    print(f"TRANSACTION_COUNT={transaction_count}")
    print(f"JOURNAL_COUNT={journal_count}")

finally:
    conn.close()
PY

echo
echo "======================================================================"
echo "15.2.8-C.16-C — FINAL FORENSIC CLASSIFICATION"
echo "======================================================================"

if [ "$PY_COMPILE_RC" -eq 0 ]; then
    echo "PY_COMPILE=PASS"
else
    echo "PY_COMPILE=FAIL"
fi

echo
echo "CLASSIFICATION_REQUIRES_REVIEW_OF_ABOVE_EVIDENCE"
echo "NO_PRODUCTION_MODIFICATION=TRUE"
echo "DATABASE_ACCESS=READ_ONLY"
echo
echo "======================================================================"
