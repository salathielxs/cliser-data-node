#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-H"
echo "MIGRATION TARGET MATRIX — READ ONLY"
echo "======================================================================"

cd "$ROOT" || exit 1

echo
echo "[1] PROCURANDO CONSUMIDORES DE node.transaction.recover_*"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import.*recover_|from node\.transaction import \(|recover_transaction|recover_pending_transactions' \
  tests scripts node api 2>/dev/null \
  | grep -vE \
    'run_1528c14h_migration_target_matrix\.sh' \
  || true

echo
echo "[2] IMPORTS DIRETOS DE node.transaction"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import' \
  tests scripts node api 2>/dev/null \
  | grep -E \
    'recover_transaction|recover_pending_transactions' \
  || true

echo
echo "[3] CHAMADAS DIRETAS"
echo "----------------------------------------------------------------------"

grep -RniE \
  '(^|[^[:alnum:]_])(recover_transaction|recover_pending_transactions)[[:space:]]*\(' \
  tests scripts node api 2>/dev/null \
  | grep -vE \
    'def (recover_transaction|recover_pending_transactions)' \
  || true

echo
echo "[4] CONSUMIDORES DO Recovery Engine OFICIAL"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.recovery import|import node\.recovery' \
  tests scripts node api 2>/dev/null \
  || true

echo
echo "[5] CONSUMIDORES DO MODELO EXPERIMENTAL"
echo "----------------------------------------------------------------------"

grep -RniE \
  'RecoveryAction|RecoveryState|RecoveryEngine|TransactionProcessor' \
  tests scripts node api 2>/dev/null \
  || true

echo
echo "[6] CONTRATOS DE AÇÃO ENCONTRADOS"
echo "----------------------------------------------------------------------"

grep -RniE \
  'action.*(COMMIT|ROLLBACK|NOOP|NOT_FOUND|COMMIT_FINALIZED|REVERIFY|FINALIZE|RECOVER|COMPLETE|QUARANTINE)' \
  tests scripts node api 2>/dev/null \
  || true

echo
echo "[7] EXPECTATIVAS DE CAMPOS DE RECOVERY"
echo "----------------------------------------------------------------------"

grep -RniE \
  'result\[["'\''](transaction_id|previous_state|final_state|action|recovered|commit_marker|reason|errors|status)["'\'']\]' \
  tests scripts node api 2>/dev/null \
  || true

echo
echo "[8] DEFINIÇÕES DE RECOVERY POR CAMADA"
echo "----------------------------------------------------------------------"

echo
echo "node/:"
grep -RniE \
  '^def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
  node 2>/dev/null \
  || true

echo
echo "scripts/:"
grep -RniE \
  '^(class (RecoveryEngine|TransactionProcessor)|def recover_transaction|def recover_pending_transactions)' \
  scripts 2>/dev/null \
  || true

echo
echo "[9] CLASSIFICAÇÃO PRELIMINAR"
echo "----------------------------------------------------------------------"

echo "MIGRATE_TO_NODE_RECOVERY:"
grep -RliE \
  'from node\.transaction import.*recover_|from node\.transaction import \(' \
  tests scripts node api 2>/dev/null \
  | while read -r f; do
      if grep -qE \
        'recover_transaction|recover_pending_transactions' \
        "$f" 2>/dev/null; then
        echo "  $f"
      fi
    done

echo
echo "KEEP_INDEPENDENT — MODELO EXPERIMENTAL:"
grep -RliE \
  'RecoveryAction|RecoveryState|TransactionProcessor' \
  tests scripts 2>/dev/null \
  | while read -r f; do
      echo "  $f"
    done

echo
echo "REVIEW:"
echo "  Qualquer arquivo que:"
echo "  - importe node.transaction.recover_*"
echo "  - mas também dependa de contrato experimental;"
echo "  - ou misture mais de um Recovery Engine."

echo
echo "[10] INTEGRIDADE — NENHUMA ALTERAÇÃO"
echo "----------------------------------------------------------------------"

sha256sum node/transaction.py
sha256sum node/recovery.py

echo
echo "[11] SINTAXE"
echo "----------------------------------------------------------------------"

python -m py_compile \
  node/transaction.py \
  node/recovery.py

if [ $? -eq 0 ]; then
  echo "PY_COMPILE=PASS"
else
  echo "PY_COMPILE=FAIL"
fi

echo
echo "======================================================================"
echo "15.2.8-C.14-H=FORENSIC_MATRIX_GENERATED"
echo "MODE=READ_ONLY"
echo "CODE_MODIFICATION=NONE"
echo "======================================================================"
