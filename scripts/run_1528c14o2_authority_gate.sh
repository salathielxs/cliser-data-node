#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.14-O.2 — RECOVERY AUTHORITY CONSOLIDATION GATE"
echo "======================================================================"

echo
echo "[1] TRANSACTION.PY LEGACY RECOVERY DEFINITIONS"
echo "----------------------------------------------------------------------"

LEGACY_DEFS="$(
    grep -n -E \
      '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
      node/transaction.py \
      2>/dev/null || true
)"

if [ -n "$LEGACY_DEFS" ]; then
    echo "$LEGACY_DEFS"
    echo "TRANSACTION_LEGACY_RECOVERY=FOUND"
    RC_LEGACY=1
else
    echo "TRANSACTION_LEGACY_RECOVERY=ABSENT"
    RC_LEGACY=0
fi

echo
echo "[2] LEGACY IMPORTS FROM NODE.TRANSACTION"
echo "----------------------------------------------------------------------"

LEGACY_IMPORTS="$(
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
      --exclude='run_1528c14m_active_consumer_migration.sh' \
      --exclude='run_1528c14l_active_consumer_migration_forensic.sh' \
      --exclude='run_1528c14m_patch.sh' \
      2>/dev/null || true
)"

if [ -n "$LEGACY_IMPORTS" ]; then
    echo "$LEGACY_IMPORTS"
    echo "LEGACY_RECOVERY_IMPORTS=FOUND"
    RC_IMPORTS=1
else
    echo "LEGACY_RECOVERY_IMPORTS=ABSENT"
    RC_IMPORTS=0
fi

echo
echo "[3] RECOVERY ENGINE AUTHORITY"
echo "----------------------------------------------------------------------"

grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status|_recover_commit|_rollback_transaction)\(' \
  node/recovery.py

RC_AUTHORITY=$?

if [ "$RC_AUTHORITY" -eq 0 ]; then
    echo "RECOVERY_AUTHORITY=node.recovery"
else
    echo "RECOVERY_AUTHORITY=INVALID"
fi

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
  --exclude='run_1528c14m_active_consumer_migration.sh' \
  --exclude='run_1528c14l_active_consumer_migration_forensic.sh' \
  --exclude='run_1528c14m_patch.sh' \
  2>/dev/null || true

echo
echo "[5] TRANSACTION MODEL PURITY"
echo "----------------------------------------------------------------------"

grep -n -E \
  'class TransactionState|class Transaction|VALID_TRANSITIONS|RECOVERABLE_STATES|TERMINAL_STATES|def rollback\(' \
  node/transaction.py

RC_TRANSACTION=$?

echo
echo "[6] RECOVERY RESOURCE AUTHORITY"
echo "----------------------------------------------------------------------"

grep -n -E \
  'get_transaction_journal|commit_marker|manifest_blocks|blocks|objects|purge_manifest|purge_object_record|_cleanup_orphan_blocks|_verify_block_object|_verify_direct_object' \
  node/recovery.py \
  | head -80

RC_RESOURCE=$?

echo
echo "[7] API / RECOVERY BOUNDARY"
echo "----------------------------------------------------------------------"

API_RECOVERY="$(
    grep -RniE \
      'from node\.transaction import|from node\.recovery import|recover_transaction|recover_pending_transactions' \
      api \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$API_RECOVERY" ]; then
    echo "$API_RECOVERY"
    echo "API_RECOVERY_REFERENCES=REVIEW"
    RC_API=1
else
    echo "API_RECOVERY_REFERENCES=ABSENT"
    RC_API=0
fi

echo
echo "[8] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
  node/transaction.py \
  node/recovery.py \
  node/object_manager.py \
  node/registry.py

RC_COMPILE=$?

echo "PY_COMPILE_RC=$RC_COMPILE"

echo
echo "[9] FINAL"
echo "----------------------------------------------------------------------"

if [ "$RC_LEGACY" -eq 0 ] &&
   [ "$RC_IMPORTS" -eq 0 ] &&
   [ "$RC_AUTHORITY" -eq 0 ] &&
   [ "$RC_TRANSACTION" -eq 0 ] &&
   [ "$RC_RESOURCE" -eq 0 ] &&
   [ "$RC_API" -eq 0 ] &&
   [ "$RC_COMPILE" -eq 0 ]; then

    echo "15.2.8-C.14-O.2=PASS"
    echo "LEGACY_RECOVERY_IN_TRANSACTION=ABSENT"
    echo "LEGACY_RECOVERY_IMPORTS=ABSENT"
    echo "RECOVERY_AUTHORITY=node.recovery"
    echo "TRANSACTION_MODEL=node.transaction"
    echo "API_RECOVERY_BOUNDARY=PASS"
    echo "RESOURCE_RECOVERY_AUTHORITY=PASS"
    echo "COMPILE=PASS"

else

    echo "15.2.8-C.14-O.2=REVIEW"
    echo "LEGACY_RC=$RC_LEGACY"
    echo "IMPORTS_RC=$RC_IMPORTS"
    echo "AUTHORITY_RC=$RC_AUTHORITY"
    echo "TRANSACTION_RC=$RC_TRANSACTION"
    echo "RESOURCE_RC=$RC_RESOURCE"
    echo "API_RC=$RC_API"
    echo "COMPILE_RC=$RC_COMPILE"
fi

echo
echo "======================================================================"
echo "15.2.8-C.14-O.2 — COMPLETE"
echo "======================================================================"
