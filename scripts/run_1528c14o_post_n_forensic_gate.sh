#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.14-O — POST-N FORENSIC GATE"
echo "======================================================================"

echo
echo "[1] HASHES BASELINE"
echo "----------------------------------------------------------------------"

sha256sum \
  node/transaction.py \
  node/recovery.py \
  node/object_manager.py \
  node/registry.py

echo
echo "[2] LEGACY RECOVERY DEFINITIONS"
echo "----------------------------------------------------------------------"

LEGACY_DEF_MATCHES="$(
    grep -RniE \
      '^[[:space:]]*def (recover_transaction|recover_pending_transactions)\(' \
      node tests scripts \
      --exclude-dir=__pycache__ \
      --exclude='*.before_fix' \
      --exclude='*.backup' \
      --exclude='*.g9_backup*' \
      --exclude='run_1528c14n_remove_legacy_recovery.sh' \
      2>/dev/null || true
)"

if [ -n "$LEGACY_DEF_MATCHES" ]; then
    echo "$LEGACY_DEF_MATCHES"
    echo "LEGACY_DEFINITIONS=FOUND"
    RC_DEFINITIONS=1
else
    echo "LEGACY_DEFINITIONS=ABSENT"
    RC_DEFINITIONS=0
fi

echo
echo "[3] LEGACY IMPORTS"
echo "----------------------------------------------------------------------"

LEGACY_IMPORT_MATCHES="$(
    grep -RniE \
      'from node\.transaction import.*(recover_transaction|recover_pending_transactions)|import node\.transaction.*(recover_transaction|recover_pending_transactions)' \
      node tests scripts \
      --exclude-dir=__pycache__ \
      --exclude='*.before_fix' \
      --exclude='*.backup' \
      --exclude='*.g9_backup*' \
      --exclude='run_1528c14n_remove_legacy_recovery.sh' \
      2>/dev/null || true
)"

if [ -n "$LEGACY_IMPORT_MATCHES" ]; then
    echo "$LEGACY_IMPORT_MATCHES"
    echo "LEGACY_IMPORTS=FOUND"
    RC_IMPORTS=1
else
    echo "LEGACY_IMPORTS=ABSENT"
    RC_IMPORTS=0
fi

echo
echo "[4] RECOVERY AUTHORITY"
echo "----------------------------------------------------------------------"

echo
echo "node.recovery definitions:"
grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status|_recover_commit|_rollback_transaction)\(' \
  node/recovery.py \
  || true

echo
echo "node.recovery consumers:"
grep -RniE \
  'from node\.recovery import|import node\.recovery' \
  tests scripts node \
  --exclude-dir=__pycache__ \
  --exclude='*.before_fix' \
  --exclude='*.backup' \
  --exclude='*.g9_backup*' \
  2>/dev/null || true

echo
echo "[5] TRANSACTION MODEL PURITY"
echo "----------------------------------------------------------------------"

echo
echo "Transaction model:"
grep -n -E \
  'class TransactionState|class Transaction|VALID_TRANSITIONS|RECOVERABLE_STATES|TERMINAL_STATES' \
  node/transaction.py \
  || true

echo
echo "Recovery references inside transaction.py:"
grep -n -Ei \
  'recovery|recover|commit_marker|journal|rollback|resource|storage_path' \
  node/transaction.py \
  || true

echo
echo "[6] RECOVERY RESOURCE AUTHORITY"
echo "----------------------------------------------------------------------"

grep -n -E \
  'get_transaction_journal|commit_marker|manifest_blocks|blocks|objects|purge_manifest|purge_object_record|_cleanup_orphan_blocks|Path|read_bytes|unlink|hashlib|reconstruct_object' \
  node/recovery.py \
  || true

echo
echo "[7] API / NODE RECOVERY BOUNDARY"
echo "----------------------------------------------------------------------"

echo
echo "API recovery references:"
grep -RniE \
  'node\.recovery|recover_transaction|recover_pending_transactions|recovery_status' \
  api \
  --exclude-dir=__pycache__ \
  2>/dev/null || true

echo
echo "API direct transaction imports:"
grep -RniE \
  'node\.transaction|TransactionState|create_transaction|update_transaction_state' \
  api \
  --exclude-dir=__pycache__ \
  2>/dev/null || true

echo
echo "[8] STARTUP RECOVERY CHECK"
echo "----------------------------------------------------------------------"

echo "Application startup/lifespan references:"
grep -RniE \
  'lifespan|startup|shutdown|recover_pending_transactions|recover_transaction' \
  api node \
  --exclude-dir=__pycache__ \
  2>/dev/null || true

echo
echo "[9] COMMIT MARKER CONTRACT"
echo "----------------------------------------------------------------------"

grep -RniE \
  'commit_marker|COMMIT_MARKER|COMMIT_FINALIZED' \
  node tests scripts \
  --exclude-dir=__pycache__ \
  --exclude='*.before_fix' \
  --exclude='*.backup' \
  --exclude='*.g9_backup*' \
  2>/dev/null || true

echo
echo "[10] OBJECT IDENTITY CONTRACT"
echo "----------------------------------------------------------------------"

grep -n -E \
  'object_id = uuid\.uuid4\(\)\.hex|content_hash = hashlib\.sha256' \
  node/object_manager.py \
  || true

echo
echo "[11] PY_COMPILE — READ-ONLY VALIDATION"
echo "----------------------------------------------------------------------"

python -m py_compile \
  node/transaction.py \
  node/recovery.py \
  node/object_manager.py \
  node/registry.py \
  tests/test_commit_marker.py \
  tests/test_atomicity.py \
  tests/test_crash_recovery.py

RC_COMPILE=$?

echo "PY_COMPILE_RC=$RC_COMPILE"

echo
echo "[12] FINAL FORENSIC GATE"
echo "----------------------------------------------------------------------"

if [ "$RC_DEFINITIONS" -eq 0 ] &&
   [ "$RC_IMPORTS" -eq 0 ] &&
   [ "$RC_COMPILE" -eq 0 ]; then

    echo "15.2.8-C.14-O=PASS"
    echo "LEGACY_DEFINITIONS=ABSENT"
    echo "LEGACY_IMPORTS=ABSENT"
    echo "RECOVERY_AUTHORITY=node.recovery"
    echo "TRANSACTION_MODEL=node.transaction"
    echo "COMPILE=PASS"

else

    echo "15.2.8-C.14-O=REVIEW"

    echo "LEGACY_DEFINITIONS_RC=$RC_DEFINITIONS"
    echo "LEGACY_IMPORTS_RC=$RC_IMPORTS"
    echo "COMPILE_RC=$RC_COMPILE"
fi

echo
echo "======================================================================"
echo "15.2.8-C.14-O — FORENSIC GATE COMPLETE"
echo "======================================================================"
