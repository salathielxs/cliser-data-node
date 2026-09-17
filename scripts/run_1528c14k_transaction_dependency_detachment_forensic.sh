#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
FILE="$ROOT/node/transaction.py"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-K"
echo "TRANSACTION DEPENDENCY DETACHMENT FORENSIC"
echo "======================================================================"

cd "$ROOT" || exit 1

echo
echo "[1] HASH BASELINE"
echo "----------------------------------------------------------------------"

sha256sum "$FILE"
sha256sum node/recovery.py

echo
echo "[2] FUNÇÕES DEFINIDAS EM transaction.py"
echo "----------------------------------------------------------------------"

grep -nE \
  '^[[:space:]]*(async[[:space:]]+)?def |^[[:space:]]*class ' \
  node/transaction.py \
  || true

echo
echo "[3] USOS DE registry IMPORTS DENTRO DE transaction.py"
echo "----------------------------------------------------------------------"

for symbol in \
  get_transaction \
  get_transaction_journal \
  list_transactions \
  update_transaction_state
do
    echo
    echo "SYMBOL=$symbol"

    grep -nE \
      "\\b${symbol}\\b" \
      node/transaction.py \
      || true
done

echo
echo "[4] AST — CHAMADAS DE registry DENTRO DE transaction.py"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

path = Path("node/transaction.py")
tree = ast.parse(path.read_text())

targets = {
    "get_transaction",
    "get_transaction_journal",
    "list_transactions",
    "update_transaction_state",
}

for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue

    if isinstance(node.func, ast.Name):
        name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        name = node.func.attr
    else:
        continue

    if name in targets:
        print(
            f"CALL={name} "
            f"LINE={node.lineno}"
        )
PY

echo
echo "[5] AST — QUAL FUNÇÃO CONTÉM CADA CHAMADA"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

path = Path("node/transaction.py")
tree = ast.parse(path.read_text())

targets = {
    "get_transaction",
    "get_transaction_journal",
    "list_transactions",
    "update_transaction_state",
}

for fn in ast.walk(tree):
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        continue

    found = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue

        if name in targets:
            found.append((name, node.lineno))

    if found:
        print()
        print(f"FUNCTION={fn.name}")

        for name, line in found:
            print(
                f"  CALL={name} "
                f"LINE={line}"
            )
PY

echo
echo "[6] RECOVERY ANTIGO — DEPENDÊNCIAS EXATAS"
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

for fn in tree.body:
    if not isinstance(fn, ast.FunctionDef):
        continue

    if fn.name not in targets:
        continue

    print()
    print("=" * 70)
    print(f"FUNCTION={fn.name}")
    print("=" * 70)

    calls = []

    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        else:
            continue

        calls.append((name, node.lineno))

    for name, line in sorted(set(calls), key=lambda x: (x[1], x[0])):
        print(
            f"  CALL={name} "
            f"LINE={line}"
        )
PY

echo
echo "[7] SÍMBOLOS DO MODELO TRANSACTION QUE NÃO PODEM SER REMOVIDOS"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

path = Path("node/transaction.py")
tree = ast.parse(path.read_text())

required = {
    "Transaction",
    "TransactionState",
    "VALID_TRANSITIONS",
    "TERMINAL_STATES",
}

defined = set()

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        defined.add(node.name)
    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                defined.add(target.id)
    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            defined.add(node.target.id)

for name in sorted(required):
    print(
        f"{name}="
        f"{'PRESENT' if name in defined else 'MISSING'}"
    )
PY

echo
echo "[8] CONSUMIDORES DE Transaction / TransactionState"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.transaction import|import node\.transaction' \
  node api tests scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14k_transaction_dependency_detachment_forensic\.sh' \
  || true

echo
echo "[9] CONSUMIDORES DE RECOVERABLE_STATES"
echo "----------------------------------------------------------------------"

grep -RniE \
  'RECOVERABLE_STATES' \
  tests node api scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14k_transaction_dependency_detachment_forensic\.sh' \
  || true

echo
echo "[10] CONSUMIDORES DE _normalize_transaction_state"
echo "----------------------------------------------------------------------"

grep -RniE \
  '_normalize_transaction_state' \
  tests node api scripts 2>/dev/null \
  | grep -vE \
    '\.(before_fix|backup|bak_)|run_1528c14k_transaction_dependency_detachment_forensic\.sh' \
  || true

echo
echo "[11] RECOVERY ENGINE OFICIAL"
echo "----------------------------------------------------------------------"

grep -nE \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
  node/recovery.py \
  || true

echo
echo "[12] SINTAXE"
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
echo "[13] HASH FINAL — DEVE SER IGUAL AO BASELINE"
echo "----------------------------------------------------------------------"

sha256sum "$FILE"
sha256sum node/recovery.py

echo
echo "======================================================================"
echo "15.2.8-C.14-K=FORENSIC_COMPLETE"
echo "MODE=READ_ONLY"
echo "CODE_MODIFICATION=NONE"
echo "======================================================================"
