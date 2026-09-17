#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
TEST="$ROOT/tests/test_atomicity.py"
BACKUP="$ROOT/tests/test_atomicity.py.bak_15210_g9"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.10-G.9 — AUTOMATIC ATOMICITY CLEANUP FIX"
echo "======================================================================"

echo
echo "[1] Verificando arquivo..."
test -f "$TEST" || {
    echo "ERRO: teste não encontrado: $TEST"
    exit 1
}

echo
echo "[2] Criando backup..."
cp "$TEST" "$BACKUP" || {
    echo "ERRO: não foi possível criar backup."
    exit 1
}

echo "BACKUP: $BACKUP"

echo
echo "[3] Verificando se rebuild já existe no cleanup..."

if grep -n -A5 -B5 \
    "conn.commit()" "$TEST" | \
    grep -q "rebuild_block_ref_counts"; then

    echo "CLEANUP JÁ CONTÉM REBUILD."
    echo "Nenhuma alteração necessária."
    exit 0
fi

echo
echo "[4] Inserindo rebuild_block_ref_counts() no cleanup..."

python - <<'PY'
from pathlib import Path

path = Path("tests/test_atomicity.py")
text = path.read_text()

old = """    conn.commit()
    conn.close()

    for object_id in object_ids:
"""

new = """    conn.commit()
    conn.close()

    # Recalcula ref_count após a remoção direta das referências.
    # O cleanup do teste manipula manifest_blocks diretamente e,
    # portanto, deve restaurar a mesma invariável usada pelo Node:
    # ref_count == COUNT(manifest_blocks).
    registry.rebuild_block_ref_counts()

    for object_id in object_ids:
"""

if old not in text:
    raise SystemExit(
        "ERRO: ponto de inserção não encontrado. "
        "Nenhuma alteração aplicada."
    )

path.write_text(text.replace(old, new, 1))
print("PATCH APLICADO: OK")
PY

echo
echo "[5] Verificando alteração..."

grep -n -A12 -B8 \
    "rebuild_block_ref_counts" \
    "$TEST"

echo
echo "[6] Compilação sintática..."

PYTHONPATH="$ROOT" python -m py_compile "$TEST" || {
    echo "ERRO: falha de sintaxe."
    echo "Restaurando backup..."
    cp "$BACKUP" "$TEST"
    exit 1
}

echo "SYNTAX: PASS"

echo
echo "======================================================================"
echo "15.2.10-G.9 — PATCH APLICADO"
echo "======================================================================"
echo "BACKUP : $BACKUP"
echo "STATUS : READY FOR TEST"
echo "======================================================================"
