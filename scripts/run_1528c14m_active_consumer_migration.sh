#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/tmp/c14m_backup_$TS"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-M"
echo "ACTIVE CONSUMER MIGRATION"
echo "======================================================================"

mkdir -p "$BACKUP_DIR"

echo
echo "[1] BACKUP"
echo "----------------------------------------------------------------------"

cp tests/test_atomicity.py \
   "$BACKUP_DIR/test_atomicity.py"

cp tests/test_commit_marker.py \
   "$BACKUP_DIR/test_commit_marker.py"

cp node/transaction.py \
   "$BACKUP_DIR/transaction.py"

cp node/recovery.py \
   "$BACKUP_DIR/recovery.py"

echo "BACKUP_DIR=$BACKUP_DIR"

echo
echo "[2] HASHES ANTES"
echo "----------------------------------------------------------------------"

sha256sum node/transaction.py
sha256sum node/recovery.py
sha256sum tests/test_atomicity.py
sha256sum tests/test_commit_marker.py

echo
echo "[3] MIGRAÇÃO test_atomicity.py"
echo "----------------------------------------------------------------------"

python - <<'PY'
from pathlib import Path

path = Path("tests/test_atomicity.py")
text = path.read_text()

old = "from node.transaction import recover_pending_transactions"
new = "from node.recovery import recover_pending_transactions"

if old not in text:
    raise SystemExit(
        "ABORT: import esperado não encontrado em test_atomicity.py"
    )

text = text.replace(old, new, 1)

path.write_text(text)
print("test_atomicity.py: IMPORT_MIGRATED=YES")
PY

echo
echo "[4] MIGRAÇÃO test_commit_marker.py"
echo "----------------------------------------------------------------------"

python - <<'PY'
from pathlib import Path

path = Path("tests/test_commit_marker.py")
text = path.read_text()

old_import = """from node.transaction import (
    recover_transaction,
    recover_pending_transactions,
)"""

new_import = """from node.recovery import (
    recover_transaction,
    recover_pending_transactions,
)"""

if old_import not in text:
    raise SystemExit(
        "ABORT: import esperado não encontrado em test_commit_marker.py"
    )

text = text.replace(old_import, new_import, 1)

old_action = 'assert result["action"] == "COMMIT_FINALIZED"'
new_action = 'assert result["action"] == "COMMIT"'

if old_action not in text:
    raise SystemExit(
        "ABORT: contrato COMMIT_FINALIZED não encontrado"
    )

text = text.replace(old_action, new_action, 1)

path.write_text(text)

print("test_commit_marker.py: IMPORT_MIGRATED=YES")
print("test_commit_marker.py: ACTION_CONTRACT_MIGRATED=COMMIT")
PY

echo
echo "[5] DIFF"
echo "----------------------------------------------------------------------"

git diff -- \
    tests/test_atomicity.py \
    tests/test_commit_marker.py \
    || true

echo
echo "[6] HASHES APÓS MIGRAÇÃO"
echo "----------------------------------------------------------------------"

sha256sum node/transaction.py
sha256sum node/recovery.py
sha256sum tests/test_atomicity.py
sha256sum tests/test_commit_marker.py

echo
echo "[7] VERIFICAÇÃO — node/transaction.py NÃO PODE TER MUDADO"
echo "----------------------------------------------------------------------"

CURRENT_TRANSACTION_HASH="$(sha256sum node/transaction.py | awk '{print $1}')"
BACKUP_TRANSACTION_HASH="$(sha256sum "$BACKUP_DIR/transaction.py" | awk '{print $1}')"

if [ "$CURRENT_TRANSACTION_HASH" = "$BACKUP_TRANSACTION_HASH" ]; then
    echo "TRANSACTION_HASH=UNCHANGED"
else
    echo "TRANSACTION_HASH=CHANGED"
    exit 1
fi

echo
echo "[8] VERIFICAÇÃO DOS IMPORTS"
echo "----------------------------------------------------------------------"

grep -nE \
  'from node\.(transaction|recovery) import' \
  tests/test_atomicity.py \
  tests/test_commit_marker.py

echo
echo "[9] VERIFICAÇÃO DO CONTRATO"
echo "----------------------------------------------------------------------"

grep -nE \
  'COMMIT_FINALIZED|action.*COMMIT|recover_transaction|recover_pending_transactions' \
  tests/test_atomicity.py \
  tests/test_commit_marker.py \
  || true

echo
echo "[10] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
    tests/test_atomicity.py \
    tests/test_commit_marker.py \
    node/transaction.py \
    node/recovery.py

if [ $? -ne 0 ]; then
    echo "PY_COMPILE=FAIL"
    exit 1
fi

echo "PY_COMPILE=PASS"

echo
echo "[11] TESTE test_commit_marker.py"
echo "----------------------------------------------------------------------"

python tests/test_commit_marker.py

COMMIT_RC=$?

echo
echo "TEST_COMMIT_MARKER_RC=$COMMIT_RC"

if [ "$COMMIT_RC" -ne 0 ]; then
    echo "TEST_COMMIT_MARKER=FAIL"
    exit 1
fi

echo
echo "[12] TESTE test_atomicity.py"
echo "----------------------------------------------------------------------"

python tests/test_atomicity.py

ATOMICITY_RC=$?

echo
echo "TEST_ATOMICITY_RC=$ATOMICITY_RC"

if [ "$ATOMICITY_RC" -ne 0 ]; then
    echo "TEST_ATOMICITY=FAIL"
    exit 1
fi

echo
echo "[13] BUSCA DE IMPORTS LEGACY"
echo "----------------------------------------------------------------------"

LEGACY_IMPORTS="$(
    grep -RniE \
      'from node\.transaction import.*recover_|from node\.transaction import \(' \
      tests node api scripts 2>/dev/null \
      | grep -vE \
        '\.(before_fix|backup|bak_)|run_1528c14m_active_consumer_migration\.sh' \
      || true
)"

if [ -n "$LEGACY_IMPORTS" ]; then
    echo "$LEGACY_IMPORTS"
    echo "LEGACY_RECOVERY_IMPORTS=FOUND"
    exit 1
else
    echo "LEGACY_RECOVERY_IMPORTS=NONE"
fi

echo
echo "[14] HASHES FINAIS"
echo "----------------------------------------------------------------------"

sha256sum node/transaction.py
sha256sum node/recovery.py
sha256sum tests/test_atomicity.py
sha256sum tests/test_commit_marker.py

echo
echo "======================================================================"
echo "15.2.8-C.14-M=PASS"
echo "ACTIVE_CONSUMERS=MIGRATED"
echo "RECOVERY_AUTHORITY=node.recovery"
echo "TRANSACTION_MODEL=node.transaction"
echo "======================================================================"
