#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
FILE="$ROOT/node/transaction.py"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-J"
echo "REMOVAL SAFETY GATE"
echo "======================================================================"

cd "$ROOT" || exit 1

echo
echo "[1] HASH BASELINE"
echo "----------------------------------------------------------------------"
sha256sum "$FILE"
sha256sum node/recovery.py

echo
echo "[2] _normalize_transaction_state — TODOS OS USOS ATIVOS"
echo "----------------------------------------------------------------------"

grep -RniE \
  '_normalize_transaction_state' \
  node api tests scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14j_removal_safety_gate\.sh' \
  || true

echo
echo "[3] DEFINIÇÃO _normalize_transaction_state"
echo "----------------------------------------------------------------------"

grep -n -A10 -B3 \
  '^def _normalize_transaction_state' \
  node/transaction.py \
  || true

echo
echo "[4] RECOVERABLE_STATES — TODOS OS USOS ATIVOS"
echo "----------------------------------------------------------------------"

grep -RniE \
  'RECOVERABLE_STATES' \
  node api tests scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14j_removal_safety_gate\.sh' \
  || true

echo
echo "[5] get_transaction_journal — TODOS OS USOS EM transaction.py"
echo "----------------------------------------------------------------------"

grep -nE \
  'get_transaction_journal' \
  node/transaction.py \
  || true

echo
echo "[6] IMPORTS DO registry EM transaction.py"
echo "----------------------------------------------------------------------"

sed -n '1,20p' node/transaction.py

echo
echo "[7] DEFINIÇÕES DO RECOVERY ANTIGO"
echo "----------------------------------------------------------------------"

grep -nE \
  '^def (recover_transaction|recover_pending_transactions)\(' \
  node/transaction.py \
  || true

echo
echo "[8] CONSUMIDORES ATIVOS DE RECOVERY ANTIGO"
echo "----------------------------------------------------------------------"

grep -RniE \
  'recover_transaction|recover_pending_transactions' \
  tests scripts node api 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14j_removal_safety_gate\.sh|^node/transaction.py:' \
  || true

echo
echo "[9] IMPORTS DE node.transaction COM RECOVERY — AST"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

targets = {
    "recover_transaction",
    "recover_pending_transactions",
}

roots = [
    Path("tests"),
    Path("scripts"),
    Path("node"),
    Path("api"),
]

for root in roots:
    if not root.exists():
        continue

    for path in sorted(root.rglob("*.py")):
        name = str(path)

        if any(x in name for x in (
            ".before_fix",
            ".backup",
            ".bak_",
        )):
            continue

        try:
            tree = ast.parse(path.read_text())
        except Exception:
            continue

        for item in ast.walk(tree):
            if not isinstance(item, ast.ImportFrom):
                continue

            if item.module != "node.transaction":
                continue

            found = sorted(
                alias.name
                for alias in item.names
                if alias.name in targets
            )

            if found:
                print(
                    f"{path}: IMPORTS={','.join(found)}"
                )
PY

echo
echo "[10] IMPORTS DE TRANSACTION / TRANSACTIONSTATE"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import|import node\.transaction' \
  node api tests scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14j_removal_safety_gate\.sh' \
  | head -200 \
  || true

echo
echo "[11] CONSUMIDORES DO Recovery Engine OFICIAL"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.recovery import|import node\.recovery' \
  node api tests scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14j_removal_safety_gate\.sh' \
  || true

echo
echo "[12] SÍMBOLOS ATUAIS"
echo "----------------------------------------------------------------------"

python - <<'PY'
import node.transaction as t

for name in (
    "recover_transaction",
    "recover_pending_transactions",
    "_normalize_transaction_state",
    "RECOVERABLE_STATES",
    "Transaction",
    "TransactionState",
):
    print(f"{name}={hasattr(t, name)}")
PY

echo
echo "[13] SINTAXE"
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
echo "[14] HASH FINAL"
echo "----------------------------------------------------------------------"

sha256sum "$FILE"
sha256sum node/recovery.py

echo
echo "======================================================================"
echo "15.2.8-C.14-J=FORENSIC_COMPLETE"
echo "MODE=READ_ONLY"
echo "CODE_MODIFICATION=NONE"
echo "======================================================================"
