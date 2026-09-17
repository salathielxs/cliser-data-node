#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
OUT="$ROOT/tmp/15.2.8-C.12-test-migration-compatibility-forensic.txt"

mkdir -p "$ROOT/tmp"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.12"
echo "TEST MIGRATION & COMPATIBILITY FORENSIC"
echo "======================================================================"
echo
echo "REGRA: ZERO ALTERACOES DE CODIGO."
echo

echo "[1] TESTES — IMPORTS"
grep -RniE 'from node\.(transaction|recovery) import|import node\.(transaction|recovery)' "$ROOT/tests" --include='*.py' 2>/dev/null || true

echo
echo "[2] TESTES — CHAMADAS DE RECOVERY"
grep -RniE 'recover_transaction[[:space:]]*\(|recover_pending_transactions[[:space:]]*\(|recovery_status[[:space:]]*\(' "$ROOT/tests" --include='*.py' 2>/dev/null || true

echo
echo "[3] ATOMICITY"
if [ -f "$ROOT/tests/test_atomicity.py" ]; then
    sed -n '470,510p' "$ROOT/tests/test_atomicity.py"
fi

echo
echo "[4] COMMIT MARKER"
if [ -f "$ROOT/tests/test_commit_marker.py" ]; then
    sed -n '1,180p' "$ROOT/tests/test_commit_marker.py"
fi

echo
echo "[5] CRASH RECOVERY"
if [ -f "$ROOT/tests/test_crash_recovery.py" ]; then
    grep -n -A20 -B12 -E 'recover_transaction|COMMITTED|ROLLBACK|NOOP' "$ROOT/tests/test_crash_recovery.py" 2>/dev/null || true
fi

echo
echo "[6] TRANSACTION.PY"
grep -n -A100 -B10 '^def recover_transaction\|^def recover_pending_transactions' "$ROOT/node/transaction.py" 2>/dev/null || true

echo
echo "[7] RECOVERY.PY"
grep -n -A130 -B15 '^def recover_transaction\|^def recover_pending_transactions' "$ROOT/node/recovery.py" 2>/dev/null || true

echo
echo "[8] RESOURCE OPERATIONS — TRANSACTION"
grep -nE 'purge_manifest|purge_object_record|mark_block_deleted|remove_block_record|rebuild_block_ref_counts|unlink|reconstruct_object|get_object|manifest_blocks|blocks|objects' "$ROOT/node/transaction.py" 2>/dev/null || true

echo
echo "[9] RESOURCE OPERATIONS — RECOVERY"
grep -nE 'purge_manifest|purge_object_record|mark_block_deleted|remove_block_record|rebuild_block_ref_counts|unlink|reconstruct_object|get_object|manifest_blocks|blocks|objects' "$ROOT/node/recovery.py" 2>/dev/null || true

echo
echo "[10] IDEMPOTENCY / SHARED BLOCKS"
grep -RniE 'idempot|second|twice|repeat|shared|ref_count|orphan|manifest_blocks' "$ROOT/tests" --include='*.py' 2>/dev/null || true

echo
echo "[11] PYTEST COLLECTION"
cd "$ROOT"
python -m pytest --collect-only -q \
tests/test_atomicity.py \
tests/test_commit_marker.py \
tests/test_crash_recovery.py \
tests/test_recovery_idempotency.py \
tests/test_transaction_failure_rollback.py \
tests/test_transaction_recovery.py \
2>&1 || true

echo
echo "[12] GIT STATUS"
git status --short 2>/dev/null || true

echo
echo "======================================================================"
echo "C.12 — MIGRATION MATRIX"
echo "======================================================================"
echo "TransactionState: PRESERVE"
echo "Transaction: PRESERVE"
echo "Recovery Authority: node.recovery"
echo "Commit Marker: PRESERVE"
echo "Journal: PRESERVE"
echo "Rollback Invariants: PRESERVE"
echo "Idempotency: PRESERVE"
echo "Shared Block Safety: PRESERVE"
echo "Startup Recovery: DEFERRED"
echo
echo "CLASSIFICATION=REVIEW_PENDING"
echo "======================================================================"
echo "15.2.8-C.12 — FIM"
echo "======================================================================"

} | tee "$OUT"

echo
echo "RELATORIO:"
echo "$OUT"
