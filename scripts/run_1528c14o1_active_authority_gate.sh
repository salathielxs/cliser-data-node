#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.14-O.1 — ACTIVE AUTHORITY FORENSIC GATE"
echo "======================================================================"

echo
echo "[1] ACTIVE LEGACY DEFINITIONS"
echo "----------------------------------------------------------------------"

ACTIVE_DEFS="$(
    grep -RniE \
      '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
      node tests scripts \
      --exclude-dir=__pycache__ \
      --exclude='*.before_fix' \
      --exclude='*.before_journal_recovery' \
      --exclude='*.backup' \
      --exclude='*.g9_backup*' \
      --exclude='*.pre_*' \
      --exclude='*.before_*' \
      --exclude='run_1528c14n_remove_legacy_recovery.sh' \
      --exclude='run_1528c14m_active_consumer_migration.sh' \
      --exclude='run_1528c14l_active_consumer_migration_forensic.sh' \
      --exclude='run_1528c14m_patch.sh' \
      2>/dev/null || true
)"

if [ -n "$ACTIVE_DEFS" ]; then
    echo "$ACTIVE_DEFS"
    echo "ACTIVE_LEGACY_DEFINITIONS=FOUND"
    RC_DEFS=1
else
    echo "ACTIVE_LEGACY_DEFINITIONS=ABSENT"
    RC_DEFS=0
fi

echo
echo "[2] ACTIVE LEGACY IMPORTS"
echo "----------------------------------------------------------------------"

ACTIVE_IMPORTS="$(
    grep -RniE \
      'from node\.transaction import.*(recover_transaction|recover_pending_transactions)|import node\.transaction.*(recover_transaction|recover_pending_transactions)' \
      node tests scripts \
      --exclude-dir=__pycache__ \
      --exclude='*.before_fix' \
      --exclude='*.before_journal_recovery' \
      --exclude='*.backup' \
      --exclude='*.g9_backup*' \
      --exclude='*.pre_*' \
      --exclude='*.before_*' \
      --exclude='run_1528c14n_remove_legacy_recovery.sh' \
      --exclude='run_1528c14m_active_consumer_migration.sh' \
      --exclude='run_1528c14l_active_consumer_migration_forensic.sh' \
      --exclude='run_1528c14m_patch.sh' \
      2>/dev/null || true
)"

if [ -n "$ACTIVE_IMPORTS" ]; then
    echo "$ACTIVE_IMPORTS"
    echo "ACTIVE_LEGACY_IMPORTS=FOUND"
    RC_IMPORTS=1
else
    echo "ACTIVE_LEGACY_IMPORTS=ABSENT"
    RC_IMPORTS=0
fi

echo
echo "[3] ACTIVE RECOVERY AUTHORITY"
echo "----------------------------------------------------------------------"

grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status|_recover_commit|_rollback_transaction)\(' \
  node/recovery.py

echo
echo "[4] ACTIVE RECOVERY CONSUMERS"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.recovery import|import node\.recovery' \
  tests scripts node \
  --exclude-dir=__pycache__ \
  --exclude='*.before_fix' \
  --exclude='*.before_journal_recovery' \
  --exclude='*.backup' \
  --exclude='*.g9_backup*' \
  --exclude='*.pre_*' \
  --exclude='*.before_*' \
  --exclude='run_1528c14n_remove_legacy_recovery.sh' \
  --exclude='run_1528c14m_active_consumer_migration.sh' \
  --exclude='run_1528c14l_active_consumer_migration_forensic.sh' \
  --exclude='run_1528c14m_patch.sh' \
  2>/dev/null || true

echo
echo "[5] TRANSACTION.PY AUTHORITY CHECK"
echo "----------------------------------------------------------------------"

grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
  node/transaction.py \
  || true

echo "TRANSACTION_RECOVERY_FUNCTIONS_EXPECTED=ABSENT"

echo
echo "[6] RECOVERY IMPORTS FROM TRANSACTION"
echo "----------------------------------------------------------------------"

grep -n -E \
  '^from node\.transaction import|^import node\.transaction' \
  node/recovery.py \
  || true

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

echo
echo "[8] FINAL"
echo "----------------------------------------------------------------------"

if [ "$RC_DEFS" -eq 0 ] &&
   [ "$RC_IMPORTS" -eq 0 ] &&
   [ "$RC_COMPILE" -eq 0 ]; then

    echo "15.2.8-C.14-O.1=PASS"
    echo "ACTIVE_LEGACY_DEFINITIONS=ABSENT"
    echo "ACTIVE_LEGACY_IMPORTS=ABSENT"
    echo "RECOVERY_AUTHORITY=node.recovery"
    echo "TRANSACTION_MODEL=node.transaction"
    echo "COMPILE=PASS"

else

    echo "15.2.8-C.14-O.1=REVIEW"
    echo "ACTIVE_DEFINITIONS_RC=$RC_DEFS"
    echo "ACTIVE_IMPORTS_RC=$RC_IMPORTS"
    echo "COMPILE_RC=$RC_COMPILE"
fi

echo
echo "======================================================================"
echo "15.2.8-C.14-O.1 — COMPLETE"
echo "======================================================================"
