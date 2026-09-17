#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.14-L"
echo "ACTIVE CONSUMER MIGRATION FORENSIC"
echo "======================================================================"

cd "$ROOT" || exit 1

echo
echo "[1] HASH BASELINE"
echo "----------------------------------------------------------------------"

sha256sum node/transaction.py
sha256sum node/recovery.py
sha256sum tests/test_atomicity.py
sha256sum tests/test_commit_marker.py

echo
echo "[2] IMPORTS DOS CONSUMIDORES LEGACY"
echo "----------------------------------------------------------------------"

echo
echo "--- tests/test_atomicity.py ---"
sed -n '1,35p' tests/test_atomicity.py

echo
echo "--- tests/test_commit_marker.py ---"
sed -n '1,35p' tests/test_commit_marker.py

echo
echo "[3] test_atomicity.py — CONTEXTO DO RECOVERY"
echo "----------------------------------------------------------------------"

sed -n '450,515p' tests/test_atomicity.py

echo
echo "[4] test_commit_marker.py — TESTE COMPLETO DE RECOVERY"
echo "----------------------------------------------------------------------"

sed -n '80,180p' tests/test_commit_marker.py

echo
echo "[5] CONTRATOS LEGACY ESPERADOS"
echo "----------------------------------------------------------------------"

grep -nE \
  'recover_transaction|recover_pending_transactions|COMMIT_FINALIZED|COMMIT|ROLLBACK|NOOP|recovered|previous_state|final_state|errors|total_pending|processed|noop' \
  tests/test_atomicity.py \
  tests/test_commit_marker.py \
  || true

echo
echo "[6] CONTRATO OFICIAL — node.recovery"
echo "----------------------------------------------------------------------"

python - <<'PY'
import inspect
import node.recovery as recovery

print("recover_transaction:")
print(inspect.signature(recovery.recover_transaction))
print()

print("recover_pending_transactions:")
print(inspect.signature(recovery.recover_pending_transactions))
print()

print("recovery_status:")
print(inspect.signature(recovery.recovery_status))
print()

print("INDIVIDUAL_SOURCE:")
print(inspect.getsource(recovery.recover_transaction))

print()
print("BATCH_SOURCE:")
print(inspect.getsource(recovery.recover_pending_transactions))
PY

echo
echo "[7] IMPORTS AST — CONSUMIDORES LEGACY"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

for filename in (
    "tests/test_atomicity.py",
    "tests/test_commit_marker.py",
):
    path = Path(filename)
    tree = ast.parse(path.read_text())

    print()
    print(f"FILE={filename}")

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "node.transaction":
                print(
                    "  IMPORT="
                    + ",".join(alias.name for alias in node.names)
                )
PY

echo
echo "[8] IMPORTS AST — TARGET OFICIAL"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

for filename in (
    "tests/test_atomicity.py",
    "tests/test_commit_marker.py",
):
    path = Path(filename)
    tree = ast.parse(path.read_text())

    print()
    print(f"FILE={filename}")

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "node.recovery":
                print(
                    "  IMPORT="
                    + ",".join(alias.name for alias in node.names)
                )
PY

echo
echo "[9] CHAMADAS AST DOS RECOVERY"
echo "----------------------------------------------------------------------"

python - <<'PY'
import ast
from pathlib import Path

targets = {
    "recover_transaction",
    "recover_pending_transactions",
}

for filename in (
    "tests/test_atomicity.py",
    "tests/test_commit_marker.py",
):
    path = Path(filename)
    tree = ast.parse(path.read_text())

    print()
    print(f"FILE={filename}")

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
                f"  CALL={name} "
                f"LINE={node.lineno}"
            )
PY

echo
echo "[10] TESTES INDIVIDUAIS EXISTENTES"
echo "----------------------------------------------------------------------"

grep -nE \
  '^[[:space:]]*(def|async def)[[:space:]]+test_' \
  tests/test_atomicity.py \
  tests/test_commit_marker.py \
  || true

echo
echo "[11] REFERÊNCIAS AO CONTRATO OFICIAL EM test_crash_recovery.py"
echo "----------------------------------------------------------------------"

grep -n -A8 -B8 \
  -E 'action.*COMMIT|action.*ROLLBACK|action.*NOOP|commit_marker|recovered' \
  tests/test_crash_recovery.py \
  || true

echo
echo "[12] SINTAXE"
echo "----------------------------------------------------------------------"

python -m py_compile \
  tests/test_atomicity.py \
  tests/test_commit_marker.py \
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

sha256sum node/transaction.py
sha256sum node/recovery.py
sha256sum tests/test_atomicity.py
sha256sum tests/test_commit_marker.py

echo
echo "======================================================================"
echo "15.2.8-C.14-L=FORENSIC_COMPLETE"
echo "MODE=READ_ONLY"
echo "CODE_MODIFICATION=NONE"
echo "======================================================================"
