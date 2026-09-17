#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
OUT="$ROOT/tmp/15.2.8-C-transaction-boundary-forensic.txt"

mkdir -p "$ROOT/tmp"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C TRANSACTION BOUNDARY FORENSIC"
echo "======================================================================"
echo "ROOT=$ROOT"
echo "DATE=$(date '+%Y-%m-%d %H:%M:%S')"
echo

echo "[1] TRANSACTION IMPLEMENTATION"
echo "----------------------------------------------------------------------"
grep -RniE 'class Transaction|def create_transaction|def create_idempotent_transaction|def update_transaction_state|def create_transaction_journal|def update_transaction_journal|def get_transaction|def delete_transaction' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[2] TRANSACTION STATES"
echo "----------------------------------------------------------------------"
grep -RniE 'TransactionState|PENDING|PREPARING|WRITING|COMMITTING|COMMIT_MARKER|COMMITTED|ROLLBACK|FAILED|RECOVER' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[3] TRANSACTION -> JOURNAL"
echo "----------------------------------------------------------------------"
grep -RniE 'create_transaction_journal|update_transaction_journal|transaction_journal|journal_id|commit_marker|phase=' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[4] TRANSACTION -> OBJECT"
echo "----------------------------------------------------------------------"
grep -RniE 'transaction_id|tx_id|object_id.*transaction|transaction.*object' "$ROOT/node/object_manager.py" "$ROOT/node/registry.py" --include='*.py' 2>/dev/null || true
echo

echo "[5] TRANSACTION -> MANIFEST"
echo "----------------------------------------------------------------------"
grep -RniE 'transaction_id|manifest_id|create_manifest|manifest.*transaction|transaction.*manifest' "$ROOT/node/object_manager.py" "$ROOT/node/manifest.py" "$ROOT/node/registry.py" --include='*.py' 2>/dev/null || true
echo

echo "[6] COMMIT BOUNDARY"
echo "----------------------------------------------------------------------"
grep -RniE 'COMMITTING|COMMIT_MARKER|commit_marker|state.*COMMITTED|TransactionState\.COMMITTED' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[7] ROLLBACK BOUNDARY"
echo "----------------------------------------------------------------------"
grep -RniE 'ROLLBACK|rollback\(\)|conn\.rollback|commit_marker.*False|TransactionState\.ROLLBACK|delete_transaction|purge' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[8] RECOVERY BOUNDARY"
echo "----------------------------------------------------------------------"
grep -RniE 'recover|recovery|recover_transaction|recover_pending|COMMIT_MARKER|commit_marker|COMMITTING|ROLLBACK' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[9] IDEMPOTENCY TRANSACTION BOUNDARY"
echo "----------------------------------------------------------------------"
grep -RniE 'idempotency_key|create_idempotent_transaction|get_idempotent_transaction|IdempotencyConflictError|IdempotencyInProgressError|IdempotencyReplayError|idempotency_response' "$ROOT/node" --include='*.py' 2>/dev/null || true
echo

echo "[10] TRANSACTION PERSISTENCE SCHEMA"
echo "----------------------------------------------------------------------"
grep -RniE 'CREATE TABLE.*transactions|CREATE TABLE.*transaction_journal|commit_marker|idempotency_key|transaction_id|journal_id|state TEXT|operation TEXT' "$ROOT/node/registry.py" --include='*.py' 2>/dev/null || true
echo

echo "[11] OBJECT MANAGER TRANSACTION PATH"
echo "----------------------------------------------------------------------"
sed -n '150,560p' "$ROOT/node/object_manager.py" 2>/dev/null || true
echo

echo "[12] REGISTRY TRANSACTION PATH"
echo "----------------------------------------------------------------------"
sed -n '1220,1810p' "$ROOT/node/registry.py" 2>/dev/null || true
echo

echo "[13] RECOVERY IMPLEMENTATION"
echo "----------------------------------------------------------------------"
sed -n '900,1010p' "$ROOT/node/object_manager.py" 2>/dev/null || true
echo

echo "[14] API TRANSACTION ACCESS"
echo "----------------------------------------------------------------------"
grep -RniE 'transaction|transaction_service|create_transaction|update_transaction|delete_transaction|commit_marker|transaction_journal' "$ROOT/api" --include='*.py' 2>/dev/null || true
echo

echo "[15] API DIRECT TRANSACTION MUTATION"
echo "----------------------------------------------------------------------"
grep -RniE 'conn\.execute|sqlite3|connect\(|BEGIN|ROLLBACK|COMMIT|transaction_journal|transactions' "$ROOT/api" --include='*.py' 2>/dev/null || true
echo

echo "[16] TRANSACTION TEST COVERAGE"
echo "----------------------------------------------------------------------"
grep -RniE 'transaction|rollback|commit|recovery|idempotency|journal|commit_marker' "$ROOT/tests" --include='*.py' 2>/dev/null || true
echo

echo "[17] ARCHITECTURE BRIDGE"
echo "----------------------------------------------------------------------"
grep -niE 'Transaction Boundary|transaction boundary|commit|rollback|recovery|idempotency|Node Core|API Layer' "$ROOT/docs/architecture/ARCHITECTURE_BRIDGE_15_2_8.md" 2>/dev/null || true
echo

echo "[18] SUMMARY"
echo "----------------------------------------------------------------------"

NODE_TX=$(grep -RniE 'class Transaction|def create_transaction|def create_idempotent_transaction|def update_transaction_state|def create_transaction_journal|def update_transaction_journal|def get_transaction|def delete_transaction' "$ROOT/node" --include='*.py' 2>/dev/null | wc -l)

API_TX=$(grep -RniE 'conn\.execute|sqlite3|connect\(|BEGIN|ROLLBACK|COMMIT|transaction_journal|transactions' "$ROOT/api" --include='*.py' 2>/dev/null | wc -l)

NODE_JOURNAL=$(grep -RniE 'transaction_journal|create_transaction_journal|update_transaction_journal|commit_marker' "$ROOT/node" --include='*.py' 2>/dev/null | wc -l)

NODE_RECOVERY=$(grep -RniE 'recover|recovery|recover_transaction|recover_pending|COMMIT_MARKER|COMMITTING|ROLLBACK' "$ROOT/node" --include='*.py' 2>/dev/null | wc -l)

echo "NODE_TRANSACTION_REFERENCES=$NODE_TX"
echo "API_TRANSACTION_MUTATION_MATCHES=$API_TX"
echo "NODE_JOURNAL_REFERENCES=$NODE_JOURNAL"
echo "NODE_RECOVERY_REFERENCES=$NODE_RECOVERY"
echo

if [ "$API_TX" -eq 0 ] && [ "$NODE_TX" -gt 0 ] && [ "$NODE_JOURNAL" -gt 0 ] && [ "$NODE_RECOVERY" -gt 0 ]; then
    echo "RESULT=PASS — fronteira transacional concentrada no Node Core"
else
    echo "RESULT=REVIEW — revisar evidências antes da classificação"
fi

echo
echo "======================================================================"
echo "END OF 15.2.8-C FORENSIC"
echo "======================================================================"

} | tee "$OUT"

echo
echo "Relatório salvo em:"
echo "$OUT"
