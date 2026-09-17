#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/tmp/c14m_patch_backup_$TS"

RECOVERY="$ROOT/node/recovery.py"
TEST="$ROOT/tests/test_commit_marker.py"

mkdir -p "$BACKUP_DIR"

echo "======================================================================"
echo "C.14-M — CONTROLLED PATCH"
echo "======================================================================"

echo
echo "[1] BACKUP"
echo "----------------------------------------------------------------------"

cp "$RECOVERY" "$BACKUP_DIR/recovery.py"
cp "$TEST" "$BACKUP_DIR/test_commit_marker.py"

echo "BACKUP_DIR=$BACKUP_DIR"

echo
echo "[2] HASHES BEFORE"
echo "----------------------------------------------------------------------"

sha256sum \
    "$RECOVERY" \
    "$TEST"

RECOVERY_BEFORE="$(sha256sum "$RECOVERY" | awk '{print $1}')"
TEST_BEFORE="$(sha256sum "$TEST" | awk '{print $1}')"

echo
echo "[3] PATCH _verify_direct_object"
echo "----------------------------------------------------------------------"

python - "$RECOVERY" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

old = """    calculated = hashlib.sha256(data).hexdigest()

    return calculated == content_hash == object_id
"""

new = """    calculated = hashlib.sha256(data).hexdigest()

    return calculated == content_hash
"""

if text.count(old) != 1:
    raise SystemExit(
        "PATCH_ABORTED: trecho esperado de _verify_direct_object não encontrado exatamente uma vez."
    )

path.write_text(text.replace(old, new, 1))
print("RECOVERY_PATCH=APPLIED")
PY

echo
echo "[4] PATCH TEST FIXTURE"
echo "----------------------------------------------------------------------"

python - "$TEST" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

old_import = """from node import registry
from node import namespace_manager
from node.recovery import (
"""

new_import = """from node import registry
from node import namespace_manager
from node.storage import OBJECTS_DIR
from node.recovery import (
"""

if text.count(old_import) != 1:
    raise SystemExit(
        "PATCH_ABORTED: bloco de imports não encontrado exatamente uma vez."
    )

text = text.replace(old_import, new_import, 1)

old_constants = """TEST_NS = "commit_marker_test"
TX_ID = "tx-commit-marker-test"
OBJECT_ID = "object-commit-marker-test"
"""

new_constants = """TEST_NS = "commit_marker_test"
TX_ID = "tx-commit-marker-test"
OBJECT_ID = "object-commit-marker-test"
TEST_DATA = b"CLISER-COMMIT-MARKER-TEST"
TEST_OBJECT_PATH = OBJECTS_DIR / OBJECT_ID
"""

if text.count(old_constants) != 1:
    raise SystemExit(
        "PATCH_ABORTED: bloco de constantes não encontrado exatamente uma vez."
    )

text = text.replace(old_constants, new_constants, 1)

old_cleanup = """def cleanup():
    conn = registry.connect()

    conn.execute(
"""

new_cleanup = """def cleanup():
    try:
        if TEST_OBJECT_PATH.exists():
            TEST_OBJECT_PATH.unlink()
    except Exception:
        pass

    conn = registry.connect()

    conn.execute(
"""

if text.count(old_cleanup) != 1:
    raise SystemExit(
        "PATCH_ABORTED: função cleanup não encontrada exatamente uma vez."
    )

text = text.replace(old_cleanup, new_cleanup, 1)

old_marker = """    registry.create_transaction(
        transaction_id=TX_ID,
        object_id=OBJECT_ID,
        namespace=TEST_NS,
        operation="PUT",
        state="COMMITTING",
        metadata={
            "test": "commit_marker_recovery",
        },
    )

    registry.create_transaction_journal(
"""

new_marker = """    content_hash = __import__("hashlib").sha256(
        TEST_DATA
    ).hexdigest()

    OBJECTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    TEST_OBJECT_PATH.write_bytes(TEST_DATA)

    registry.register_object(
        object_id=OBJECT_ID,
        content_hash=content_hash,
        size=len(TEST_DATA),
        storage_path=TEST_OBJECT_PATH,
        namespace=TEST_NS,
    )

    registry.create_transaction(
        transaction_id=TX_ID,
        object_id=OBJECT_ID,
        namespace=TEST_NS,
        operation="PUT",
        state="COMMITTING",
        metadata={
            "test": "commit_marker_recovery",
        },
    )

    registry.create_transaction_journal(
"""

if text.count(old_marker) != 1:
    raise SystemExit(
        "PATCH_ABORTED: ponto de criação da transação não encontrado exatamente uma vez."
    )

text = text.replace(old_marker, new_marker, 1)

path.write_text(text)
print("TEST_FIXTURE_PATCH=APPLIED")
PY

echo
echo "[5] DIFF"
echo "----------------------------------------------------------------------"

git diff -- "$RECOVERY"
echo
git diff -- "$TEST"

echo
echo "[6] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
    "$RECOVERY" \
    "$TEST"

echo "PY_COMPILE=PASS"

echo
echo "[7] HASHES AFTER"
echo "----------------------------------------------------------------------"

sha256sum \
    "$RECOVERY" \
    "$TEST"

echo
echo "[8] VERIFY UNRELATED PRODUCTION FILES"
echo "----------------------------------------------------------------------"

sha256sum \
    node/transaction.py \
    node/object_manager.py \
    node/storage.py \
    node/registry.py

echo
echo "[9] RUN COMMIT MARKER"
echo "----------------------------------------------------------------------"

python tests/test_commit_marker.py
RC_COMMIT=$?

echo
echo "TEST_COMMIT_MARKER_RC=$RC_COMMIT"

echo
echo "[10] RUN ATOMICITY"
echo "----------------------------------------------------------------------"

python tests/test_atomicity.py
RC_ATOMICITY=$?

echo
echo "TEST_ATOMICITY_RC=$RC_ATOMICITY"

echo
echo "[11] RUN CRASH RECOVERY"
echo "----------------------------------------------------------------------"

python tests/test_crash_recovery.py
RC_CRASH=$?

echo
echo "TEST_CRASH_RECOVERY_RC=$RC_CRASH"

echo
echo "[12] VERIFY PATCH SEMANTICS"
echo "----------------------------------------------------------------------"

grep -n -A5 -B5 \
    'calculated = hashlib.sha256(data).hexdigest()' \
    node/recovery.py

echo
echo "[13] VERIFY LEGACY EQUALITY IS GONE"
echo "----------------------------------------------------------------------"

if grep -n \
    'calculated == content_hash == object_id' \
    node/recovery.py
then
    echo "LEGACY_HASH_CONTRACT=FOUND"
    RC_SEMANTIC=1
else
    echo "LEGACY_HASH_CONTRACT=ABSENT"
    RC_SEMANTIC=0
fi

echo
echo "[14] VERIFY OBJECT IDENTITY MODEL"
echo "----------------------------------------------------------------------"

grep -n \
    -E 'object_id = uuid\.uuid4\(\)\.hex|content_hash = hashlib\.sha256' \
    node/object_manager.py

echo
echo "[15] VERIFY TEST CLEANUP"
echo "----------------------------------------------------------------------"

if [ -e "storage/objects/$(
    printf '%s' 'object-commit-marker-test'
)" ]; then
    echo "TEST_PHYSICAL_FILE=RESIDUAL"
    RC_CLEANUP=1
else
    echo "TEST_PHYSICAL_FILE=ABSENT"
    RC_CLEANUP=0
fi

echo
echo "[16] FINAL STATUS"
echo "----------------------------------------------------------------------"

if [ "$RC_COMMIT" -eq 0 ] &&
   [ "$RC_ATOMICITY" -eq 0 ] &&
   [ "$RC_CRASH" -eq 0 ] &&
   [ "$RC_SEMANTIC" -eq 0 ] &&
   [ "$RC_CLEANUP" -eq 0 ]; then

    echo "15.2.8-C.14-M=PASS"
    echo "MODE=CONTROLLED_PATCH"
    echo "RECOVERY_DIRECT_HASH_CONTRACT=PASS"
    echo "COMMIT_MARKER=PASS"
    echo "ATOMICITY=PASS"
    echo "CRASH_RECOVERY=PASS"
    echo "SEMANTIC_CONTRACT=PASS"
    echo "PHYSICAL_CLEANUP=PASS"
    echo "BACKUP=$BACKUP_DIR"

    exit 0
else
    echo "15.2.8-C.14-M=FAIL"
    echo "MODE=CONTROLLED_PATCH"
    echo "COMMIT_MARKER_RC=$RC_COMMIT"
    echo "ATOMICITY_RC=$RC_ATOMICITY"
    echo "CRASH_RECOVERY_RC=$RC_CRASH"
    echo "SEMANTIC_RC=$RC_SEMANTIC"
    echo "CLEANUP_RC=$RC_CLEANUP"
    echo "BACKUP=$BACKUP_DIR"

    exit 1
fi
