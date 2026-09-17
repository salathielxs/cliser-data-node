#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
TARGET="$ROOT/node/transaction.py"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/tmp/c14n_backup_$TS"

mkdir -p "$BACKUP_DIR"

echo "======================================================================"
echo "15.2.8-C.14-N — REMOVE LEGACY RECOVERY"
echo "======================================================================"

echo
echo "[1] PRE-CHECK"
echo "----------------------------------------------------------------------"

cd "$ROOT" || exit 1

echo "TARGET=$TARGET"

echo
echo "LEGACY FUNCTIONS:"
grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
  "$TARGET" || true

echo
echo "[2] BACKUP"
echo "----------------------------------------------------------------------"

cp "$TARGET" "$BACKUP_DIR/transaction.py"

echo "BACKUP_DIR=$BACKUP_DIR"

echo
echo "[3] HASH BEFORE"
echo "----------------------------------------------------------------------"

sha256sum "$TARGET"

echo
echo "[4] AST REMOVAL"
echo "----------------------------------------------------------------------"

TARGET="$TARGET" python - <<'PY'
import ast
import os
from pathlib import Path

target = Path(os.environ["TARGET"])
source = target.read_text()

tree = ast.parse(source)

remove_names = {
    "recover_transaction",
    "recover_pending_transactions",
}

ranges = []

for node in tree.body:
    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in remove_names
    ):
        if not hasattr(node, "end_lineno"):
            raise RuntimeError(
                f"AST sem suporte a end_lineno: {node.name}"
            )

        ranges.append(
            (node.lineno, node.end_lineno, node.name)
        )

found = {name for _, _, name in ranges}
missing = remove_names - found

if missing:
    raise RuntimeError(
        "Funções legadas não encontradas: "
        + ", ".join(sorted(missing))
    )

lines = source.splitlines(keepends=True)

for start, end, name in sorted(
    ranges,
    reverse=True,
):
    print(
        f"REMOVENDO {name}: "
        f"linhas {start}-{end}"
    )

    del lines[start - 1:end]

target.write_text("".join(lines))

print("AST_REMOVAL=APPLIED")
PY

RC_AST=$?

if [ "$RC_AST" -ne 0 ]; then
    echo
    echo "AST_REMOVAL=FAIL"
    echo "RESTORING_BACKUP=YES"
    cp "$BACKUP_DIR/transaction.py" "$TARGET"
    exit 1
fi

echo
echo "[5] LEGACY FUNCTION CHECK"
echo "----------------------------------------------------------------------"

if grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
  "$TARGET"
then
    echo "LEGACY_RECOVERY_FUNCTIONS=FOUND"
    echo "RESTORING_BACKUP=YES"
    cp "$BACKUP_DIR/transaction.py" "$TARGET"
    exit 1
else
    echo "LEGACY_RECOVERY_FUNCTIONS=ABSENT"
fi

echo
echo "[6] TRANSACTION MODEL CHECK"
echo "----------------------------------------------------------------------"

grep -n -E \
  'class TransactionState|class Transaction|VALID_TRANSITIONS|RECOVERABLE_STATES|TERMINAL_STATES' \
  "$TARGET"

echo
echo "[7] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
  node/transaction.py \
  node/recovery.py \
  node/object_manager.py \
  node/registry.py

RC_COMPILE=$?

echo "PY_COMPILE_RC=$RC_COMPILE"

if [ "$RC_COMPILE" -ne 0 ]; then
    echo "COMPILE=FAIL"
    echo "RESTORING_BACKUP=YES"
    cp "$BACKUP_DIR/transaction.py" "$TARGET"
    exit 1
fi

echo "COMPILE=PASS"

echo
echo "[8] RECOVERY CONSUMERS"
echo "----------------------------------------------------------------------"

echo "node.recovery consumers:"
grep -RniE \
  'from node\.recovery import|import node\.recovery' \
  tests scripts node \
  --exclude-dir=__pycache__ \
  || true

echo
echo "[9] LEGACY IMPORT CHECK"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import.*(recover_transaction|recover_pending_transactions)' \
  tests scripts node \
  --exclude-dir=__pycache__ \
  || true

echo
echo "[10] TARGETED TESTS"
echo "----------------------------------------------------------------------"

PYTHONPATH="$ROOT" python tests/test_commit_marker.py
RC_COMMIT=$?

echo
echo "TEST_COMMIT_MARKER_RC=$RC_COMMIT"

PYTHONPATH="$ROOT" python tests/test_atomicity.py
RC_ATOMICITY=$?

echo
echo "TEST_ATOMICITY_RC=$RC_ATOMICITY"

PYTHONPATH="$ROOT" python tests/test_crash_recovery.py
RC_CRASH=$?

echo
echo "TEST_CRASH_RECOVERY_RC=$RC_CRASH"

echo
echo "[11] HASH AFTER"
echo "----------------------------------------------------------------------"

sha256sum "$TARGET"

echo
echo "[12] FINAL GATE"
echo "----------------------------------------------------------------------"

if [ "$RC_COMPILE" -eq 0 ] &&
   [ "$RC_COMMIT" -eq 0 ] &&
   [ "$RC_ATOMICITY" -eq 0 ] &&
   [ "$RC_CRASH" -eq 0 ] &&
   ! grep -q -E \
      '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
      "$TARGET"
then
    echo "15.2.8-C.14-N=PASS"
    echo "LEGACY_RECOVERY_REMOVED=PASS"
    echo "TRANSACTION_MODEL_PRESERVED=PASS"
    echo "RECOVERY_ENGINE=PRESERVED"
    echo "COMPILE=PASS"
    echo "COMMIT_MARKER=PASS"
    echo "ATOMICITY=PASS"
    echo "CRASH_RECOVERY=PASS"
else
    echo "15.2.8-C.14-N=FAIL"
    echo "RESTORING_BACKUP=YES"
    cp "$BACKUP_DIR/transaction.py" "$TARGET"

    echo
    echo "RESTORED_HASH:"
    sha256sum "$TARGET"

    exit 1
fi

echo
echo "======================================================================"
echo "15.2.8-C.14-N — COMPLETE"
echo "======================================================================"
