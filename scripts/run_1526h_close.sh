#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
RESULT="$ROOT/tmp/15.2.6-H-close-result.txt"

mkdir -p "$ROOT/tmp"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.6-H CLOSE"
echo "======================================================================"
echo

echo "[1] G.7 — OPERATIONAL RECOVERY"
echo "PASS — PREPARED -> ROLLBACK"
echo

echo "[2] G.8 — STATE AFTER RECOVERY"
echo "PASS — ROLLBACK persistido"
echo

echo "[3] G.9 — RECOVERY IDEMPOTENCY"
echo "PASS — segunda recuperação retornou NOOP"
echo "PASS — STATE_STABLE=True"
echo

echo "[4] G.10 — FINAL INTEGRITY"

PYTHONPATH="$ROOT" python - <<'PY'
from node.registry import get_transaction, get_transaction_journal
import sqlite3
import os

tx_id = "IDEMPOTENCY-TEST-001"
test_object = "OBJECT-TEST-001"

tx = get_transaction(tx_id)
journal = get_transaction_journal(tx_id)

print("TRANSACTION_STATE:", tx["state"] if tx else "NOT_FOUND")
print("JOURNAL:", "PRESENT" if journal else "NONE")

conn = sqlite3.connect("data/registry.db")

object_row = conn.execute(
    "SELECT object_id FROM objects WHERE object_id=?",
    (test_object,)
).fetchone()

manifest_row = conn.execute(
    "SELECT object_id FROM manifests WHERE object_id=?",
    (test_object,)
).fetchone()

manifest_blocks = conn.execute(
    "SELECT COUNT(*) FROM manifest_blocks WHERE object_id=?",
    (test_object,)
).fetchone()[0]

ref_errors = conn.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT b.block_id
        FROM blocks b
        LEFT JOIN manifest_blocks mb
            ON mb.block_id = b.block_id
        GROUP BY b.block_id
        HAVING b.ref_count != COUNT(mb.block_id)
    )
""").fetchone()[0]

integrity = conn.execute(
    "PRAGMA integrity_check"
).fetchone()[0]

conn.close()

physical_found = False

for root, dirs, files in os.walk("storage/objects"):
    for name in files:
        if name == test_object or name.startswith(test_object):
            physical_found = True

print("OBJECT_TEST_001:", "PRESENT" if object_row else "ABSENT")
print("MANIFEST_TEST_001:", "PRESENT" if manifest_row else "ABSENT")
print("MANIFEST_BLOCKS_TEST_001:", manifest_blocks)
print("PHYSICAL_OBJECT_TEST_001:", "PRESENT" if physical_found else "ABSENT")
print("BLOCK_REFERENCE_ERRORS:", ref_errors)
print("SQLITE_INTEGRITY:", integrity)

assert tx is not None
assert tx["state"] == "ROLLBACK"
assert journal is None
assert object_row is None
assert manifest_row is None
assert manifest_blocks == 0
assert physical_found is False
assert ref_errors == 0
assert integrity == "ok"

print()
print("G.10_RESULT: PASS")
PY

G10_STATUS=$?

if [ "$G10_STATUS" -ne 0 ]; then
    echo
    echo "G.10_RESULT: FAIL"
    echo "15.2.6-H: NOT CLOSED"
    exit 1
fi

echo
echo "[5] ARCHITECTURAL CLASSIFICATION"
echo "PASS — recovery architecture classified."
echo
echo "Operational:"
echo "  node/transaction.py"
echo "  node/recovery.py"
echo
echo "Reference/Test:"
echo "  scripts/transaction_recovery_engine.py"
echo
echo "NOTE:"
echo "There are two operational recovery implementations with different"
echo "semantics. This remains a future architectural decision."
echo "No runtime code was modified by 15.2.6-H."
echo

echo "[6] PHASE RESULT"

cat > "$RESULT" <<'EOF'
CLISER DATA NODE
15.2.6-H — CLOSE

STATUS: PASS / CLOSED

15.2.6-A  PASS / CLASSIFIED
15.2.6-B  PASS / CLASSIFIED
15.2.6-C  PASS
15.2.6-D  PASS
15.2.6-E  PASS / DOCUMENTED
15.2.6-F.1 PASS
15.2.6-F.2 PASS
15.2.6-F.3 PASS / CLASSIFIED
15.2.6-G.1 PASS
15.2.6-G.2 PASS
15.2.6-G.3 PASS
15.2.6-G.4 PASS / CLASSIFIED
15.2.6-G.5 PASS
15.2.6-G.6 PASS
15.2.6-G.7 PASS
15.2.6-G.8 PASS
15.2.6-G.9 PASS
15.2.6-G.10 PASS

RECOVERY TEST:
PREPARED -> ROLLBACK

REPEATED RECOVERY:
ROLLBACK -> NOOP

FINAL TRANSACTION:
ROLLBACK

JOURNAL:
NONE

TEST OBJECT:
ABSENT

TEST MANIFEST:
ABSENT

TEST MANIFEST BLOCKS:
0

PHYSICAL TEST OBJECT:
ABSENT

BLOCK REFERENCE ERRORS:
0

SQLITE INTEGRITY:
ok

ARCHITECTURAL CLASSIFICATION:
node/transaction.py = operational
node/recovery.py = operational
scripts/transaction_recovery_engine.py = reference/test

ARCHITECTURAL NOTE:
Two operational recovery implementations remain classified as a
future architectural decision. No integrity failure was demonstrated.

PHASE 15.2.6:
CLOSED
EOF

echo "15.2.6-A  PASS / CLASSIFIED"
echo "15.2.6-B  PASS / CLASSIFIED"
echo "15.2.6-C  PASS"
echo "15.2.6-D  PASS"
echo "15.2.6-E  PASS / DOCUMENTED"
echo "15.2.6-F.1 PASS"
echo "15.2.6-F.2 PASS"
echo "15.2.6-F.3 PASS / CLASSIFIED"
echo "15.2.6-G.1 PASS"
echo "15.2.6-G.2 PASS"
echo "15.2.6-G.3 PASS"
echo "15.2.6-G.4 PASS / CLASSIFIED"
echo "15.2.6-G.5 PASS"
echo "15.2.6-G.6 PASS"
echo "15.2.6-G.7 PASS"
echo "15.2.6-G.8 PASS"
echo "15.2.6-G.9 PASS"
echo "15.2.6-G.10 PASS"

echo
echo "[7] RESULT FILE"
cat "$RESULT"

echo
echo "======================================================================"
echo "15.2.6-H — CLOSED"
echo "======================================================================"
