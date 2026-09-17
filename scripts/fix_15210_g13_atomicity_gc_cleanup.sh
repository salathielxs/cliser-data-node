#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
TEST="$ROOT/tests/test_atomicity.py"
BACKUP="$ROOT/tests/test_atomicity.py.bak_15210_g13"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.10-G.13.1 — AUTOMATIC ATOMICITY GC CLEANUP FIX"
echo "======================================================================"

test -f "$TEST" || {
    echo "ERRO: $TEST não encontrado."
    exit 1
}

echo
echo "[1] Backup..."
cp "$TEST" "$BACKUP" || {
    echo "ERRO: backup falhou."
    exit 1
}

echo "BACKUP: $BACKUP"

echo
echo "[2] Adicionando import do GC..."

python - <<'PY'
from pathlib import Path

path = Path("tests/test_atomicity.py")
text = path.read_text()

old = """from node.recovery import recover_pending_transactions
"""

new = """from node.recovery import recover_pending_transactions
from node.object_manager import garbage_collect_blocks
"""

if "from node.object_manager import garbage_collect_blocks" not in text:
    if old not in text:
        raise SystemExit("ERRO: import anchor não encontrado.")
    text = text.replace(old, new, 1)

path.write_text(text)
print("IMPORT GC: OK")
PY

echo
echo "[3] Inserindo GC no cleanup..."

python - <<'PY'
from pathlib import Path

path = Path("tests/test_atomicity.py")
text = path.read_text()

old = """    registry.rebuild_block_ref_counts()

    for object_id in object_ids:
"""

new = """    registry.rebuild_block_ref_counts()

    # O cleanup remove diretamente as referências dos objetos de teste.
    # Após recalcular ref_count, blocos sem referências devem seguir
    # o mesmo mecanismo oficial de GC utilizado pelo Node.
    garbage_collect_blocks()

    for object_id in object_ids:
"""

if "    garbage_collect_blocks()" in text:
    print("GC JÁ PRESENTE: nenhuma alteração adicional.")
elif old not in text:
    raise SystemExit("ERRO: ponto de inserção do GC não encontrado.")
else:
    path.write_text(text.replace(old, new, 1))
    print("GC CLEANUP: OK")
PY

echo
echo "[4] Verificação..."

grep -n -A15 -B8 \
    "garbage_collect_blocks" \
    "$TEST"

echo
echo "[5] Compilação..."

PYTHONPATH="$ROOT" python -m py_compile "$TEST" || {
    echo "ERRO: sintaxe inválida."
    cp "$BACKUP" "$TEST"
    exit 1
}

echo "SYNTAX: PASS"

echo
echo "======================================================================"
echo "15.2.10-G.13.1 — PATCH COMPLETE"
echo "======================================================================"
echo "BACKUP : $BACKUP"
echo "STATUS : READY FOR REGRESSION"
echo "======================================================================"
