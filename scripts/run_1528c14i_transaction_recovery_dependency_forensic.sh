#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
FILE="$ROOT/node/transaction.py"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-I"
echo "TRANSACTION RECOVERY DEPENDENCY FORENSIC"
echo "======================================================================"

cd "$ROOT" || exit 1

echo
echo "[1] HASH ANTES"
echo "----------------------------------------------------------------------"
sha256sum "$FILE"

echo
echo "[2] DEFINIÇÃO recover_transaction()"
echo "----------------------------------------------------------------------"

sed -n \
  '/^[[:space:]]*def recover_transaction(/,/^[[:space:]]*def /p' \
  "$FILE" \
  | sed '$d'

echo
echo "[3] DEFINIÇÃO recover_pending_transactions()"
echo "----------------------------------------------------------------------"

sed -n \
  '/^[[:space:]]*def recover_pending_transactions(/,/^[[:space:]]*def /p' \
  "$FILE" \
  | sed '$d'

echo
echo "[4] REFERÊNCIAS INTERNAS A RECOVERY"
echo "----------------------------------------------------------------------"

grep -nE \
  'recover_transaction|recover_pending_transactions|RECOVERABLE_STATES|Recovery|recovery|journal|commit_marker' \
  "$FILE" \
  || true

echo
echo "[5] DEPENDÊNCIAS UTILIZADAS POR recover_transaction()"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

path = Path("node/transaction.py")
tree = ast.parse(path.read_text())

targets = {
    "recover_transaction",
    "recover_pending_transactions",
}

for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in targets:
        print()
        print("=" * 70)
        print(node.name)
        print("=" * 70)

        names = sorted({
            n.id
            for n in ast.walk(node)
            if isinstance(n, ast.Name)
        })

        attrs = sorted({
            n.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Attribute)
        })

        print("NAMES:")
        for name in names:
            print("  ", name)

        print("ATTRIBUTES:")
        for attr in attrs:
            print("  ", attr)
PY

echo
echo "[6] FUNÇÕES DO transaction.py CHAMADAS PELO RECOVERY ANTIGO"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

path = Path("node/transaction.py")
tree = ast.parse(path.read_text())

targets = {
    "recover_transaction",
    "recover_pending_transactions",
}

defs = {
    n.name
    for n in tree.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
}

for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in targets:
        calls = set()

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.add(child.func.attr)

        local = sorted(calls & defs)

        print()
        print(f"{node.name}:")
        if local:
            for item in local:
                print(f"  LOCAL_FUNCTION={item}")
        else:
            print("  LOCAL_FUNCTIONS=NONE")
PY

echo
echo "[7] CONSUMIDORES ATIVOS DE node.transaction.recover_*"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import.*recover_|recover_transaction|recover_pending_transactions' \
  tests scripts node api 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14i_transaction_recovery_dependency_forensic\.sh' \
  || true

echo
echo "[8] IMPORTS DE node.transaction POR object_manager"
echo "----------------------------------------------------------------------"

grep -n -A20 -B5 \
  'from node.transaction import' \
  node/object_manager.py \
  || true

echo
echo "[9] VERIFICAÇÃO ESPECÍFICA object_manager → recovery antigo"
echo "----------------------------------------------------------------------"

grep -nE \
  'recover_transaction|recover_pending_transactions' \
  node/object_manager.py \
  || true

echo
echo "[10] DEFINIÇÃO DE RECOVERABLE_STATES"
echo "----------------------------------------------------------------------"

grep -n -A15 -B5 \
  'RECOVERABLE_STATES' \
  node/transaction.py \
  || true

echo
echo "[11] REFERÊNCIAS AO MODEL DE TRANSACTION"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import|import node\.transaction' \
  node api tests scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14i_transaction_recovery_dependency_forensic\.sh' \
  || true

echo
echo "[12] SINTAXE"
echo "----------------------------------------------------------------------"

python -m py_compile node/transaction.py

if [ $? -eq 0 ]; then
    echo "PY_COMPILE=PASS"
else
    echo "PY_COMPILE=FAIL"
fi

echo
echo "[13] HASH DEPOIS"
echo "----------------------------------------------------------------------"

sha256sum "$FILE"

echo
echo "======================================================================"
echo "15.2.8-C.14-I=FORENSIC_COMPLETE"
echo "MODE=READ_ONLY"
echo "CODE_MODIFICATION=NONE"
echo "======================================================================"
