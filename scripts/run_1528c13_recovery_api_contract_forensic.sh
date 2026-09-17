#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
REPORT="$ROOT/tmp/15.2.8-C.13-recovery-api-contract-forensic.txt"

mkdir -p "$ROOT/tmp"

exec > >(tee "$REPORT") 2>&1

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.13"
echo "RECOVERY API CONTRACT FORENSIC"
echo "======================================================================"
echo
echo "ROOT=$ROOT"
echo "REPORT=$REPORT"
echo "MODE=READ-ONLY"
echo

cd "$ROOT" || exit 1

echo "======================================================================"
echo "[1] RECOVERY API DEFINITIONS"
echo "======================================================================"

echo
echo "--- node.transaction ---"
grep -nE \
'^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
node/transaction.py 2>/dev/null || true

echo
echo "--- node.recovery ---"
grep -nE \
'^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
node/recovery.py 2>/dev/null || true

echo

echo "======================================================================"
echo "[2] RECOVERY IMPORTS IN TESTS"
echo "======================================================================"

grep -RniE \
'from node\.(transaction|recovery) import|import node\.(transaction|recovery)' \
tests scripts \
--include='*.py' \
2>/dev/null || true

echo

echo "======================================================================"
echo "[3] RECOVERY CALL SITES"
echo "======================================================================"

grep -RniE \
'\b(recover_transaction|recover_pending_transactions|recovery_status)\s*\(' \
tests scripts node api \
--include='*.py' \
2>/dev/null || true

echo

echo "======================================================================"
echo "[4] EXPECTED ACTION VALUES"
echo "======================================================================"

grep -RniE \
'["'\''](COMMIT|COMMIT_FINALIZED|ROLLBACK|NOOP|NOT_FOUND|NOOP_UNSUPPORTED_STATE)["'\'']' \
tests \
--include='*.py' \
2>/dev/null || true

echo

echo "======================================================================"
echo "[5] EXPECTED RESULT FIELDS"
echo "======================================================================"

grep -RniE \
'\[["'\''](transaction_id|previous_state|final_state|action|recovered|errors|commit_marker|reason|results|total|processed)["'\'']\]' \
tests \
--include='*.py' \
2>/dev/null || true

echo

echo "======================================================================"
echo "[6] TRANSACTION RECOVERY CONTRACT — CURRENT"
echo "======================================================================"

sed -n '/^[[:space:]]*def recover_transaction(/,/^[[:space:]]*def /p' \
node/transaction.py 2>/dev/null | head -n 180

echo

echo "======================================================================"
echo "[7] RECOVERY ENGINE CONTRACT — CURRENT"
echo "======================================================================"

sed -n '/^[[:space:]]*def recover_transaction(/,/^[[:space:]]*def /p' \
node/recovery.py 2>/dev/null | head -n 220

echo

echo "======================================================================"
echo "[8] BATCH RECOVERY CONTRACT — TRANSACTION"
echo "======================================================================"

sed -n '/^[[:space:]]*def recover_pending_transactions(/,/^[[:space:]]*def /p' \
node/transaction.py 2>/dev/null | head -n 220

echo

echo "======================================================================"
echo "[9] BATCH RECOVERY CONTRACT — RECOVERY ENGINE"
echo "======================================================================"

sed -n '/^[[:space:]]*def recover_pending_transactions(/,/^[[:space:]]*def /p' \
node/recovery.py 2>/dev/null | head -n 220

echo

echo "======================================================================"
echo "[10] RESOURCE-AWARE RECOVERY EVIDENCE"
echo "======================================================================"

grep -nE \
'purge_manifest|purge_object_record|rebuild_block_ref_counts|mark_block_deleted|remove_block_record|manifest_blocks|blocks|objects|unlink|reconstruct_object|get_object|hashlib|Path' \
node/recovery.py \
2>/dev/null || true

echo

echo "======================================================================"
echo "[11] TRANSACTION MODEL RESOURCE ACCESS CHECK"
echo "======================================================================"

grep -nE \
'purge_manifest|purge_object_record|rebuild_block_ref_counts|mark_block_deleted|remove_block_record|manifest_blocks|blocks|objects|unlink|reconstruct_object|get_object' \
node/transaction.py \
2>/dev/null || true

echo

echo "======================================================================"
echo "[12] IDEMPOTENCY / SHARED-BLOCK TEST EVIDENCE"
echo "======================================================================"

grep -RniE \
'idempot|shared.?block|ref_count|duplicate.?commit|exactly.?once|stable.*result|result.*stable' \
tests \
--include='*.py' \
2>/dev/null || true

echo

echo "======================================================================"
echo "[13] PYTEST COLLECTION"
echo "======================================================================"

if command -v pytest >/dev/null 2>&1; then
    pytest --collect-only -q 2>&1 || true
else
    echo "pytest=NOT_FOUND"
fi

echo

echo "======================================================================"
echo "[14] GIT STATUS — VERIFY NO CODE CHANGE"
echo "======================================================================"

git status --short 2>/dev/null || true

echo

echo "======================================================================"
echo "[15] STATIC CONTRACT CLASSIFICATION"
echo "======================================================================"

ACTION_COMMIT=$(grep -RhoE '["'\'']COMMIT["'\'']' \
    tests --include='*.py' 2>/dev/null | wc -l)

ACTION_COMMIT_FINALIZED=$(grep -RhoE '["'\'']COMMIT_FINALIZED["'\'']' \
    tests --include='*.py' 2>/dev/null | wc -l)

ERRORS_EXPECTED=$(grep -RhoE '\[[[:space:]]*["'\'']errors["'\'']\][[:space:]]*' \
    tests --include='*.py' 2>/dev/null | wc -l)

echo "TEST_EXPECTS_COMMIT=$ACTION_COMMIT"
echo "TEST_EXPECTS_COMMIT_FINALIZED=$ACTION_COMMIT_FINALIZED"
echo "TEST_EXPECTS_ERRORS_FIELD=$ERRORS_EXPECTED"

if [ "$ACTION_COMMIT" -gt 0 ] && [ "$ACTION_COMMIT_FINALIZED" -gt 0 ]; then
    echo "ACTION_CONTRACT=CONFLICT"
else
    echo "ACTION_CONTRACT=NO_DIRECT_CONFLICT_DETECTED"
fi

if [ "$ERRORS_EXPECTED" -gt 0 ]; then
    echo "BATCH_CONTRACT=DICT_REPORT_REQUIRED_FOR_CURRENT_TESTS"
else
    echo "BATCH_CONTRACT=NO_ERRORS_FIELD_EXPECTATION_DETECTED"
fi

echo

echo "======================================================================"
echo "[16] TARGET ARCHITECTURE CHECK"
echo "======================================================================"

echo "TRANSACTION_MODEL=node.transaction"
echo "RECOVERY_AUTHORITY=node.recovery"
echo "REGISTRY_PERSISTENCE=node.registry"
echo "STARTUP_RECOVERY=DEFERRED"
echo "RESOURCE_VALIDATION=node.recovery"
echo "SHARED_BLOCK_PROTECTION=PRESERVE"
echo "IDEMPOTENCY=PRESERVE"

echo

echo "======================================================================"
echo "[17] FINAL FORENSIC RESULT"
echo "======================================================================"

if [ "$ACTION_COMMIT" -gt 0 ] && [ "$ACTION_COMMIT_FINALIZED" -gt 0 ]; then
    echo "RESULT=REVIEW"
    echo "REASON=ACTION_CONTRACT_REQUIRES_CANONICALIZATION"
elif [ "$ERRORS_EXPECTED" -gt 0 ]; then
    echo "RESULT=REVIEW"
    echo "REASON=BATCH_RECOVERY_CONTRACT_REQUIRES_CANONICALIZATION"
else
    echo "RESULT=REVIEW"
    echo "REASON=CONTRACT_REVIEW_REQUIRED_BEFORE_IMPLEMENTATION"
fi

echo
echo "15.2.8-C.13 COMPLETE"
echo "======================================================================"
