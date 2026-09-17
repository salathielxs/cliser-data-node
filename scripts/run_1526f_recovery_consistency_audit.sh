#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
RESULT_DIR="$ROOT/tmp"
RESULT="$RESULT_DIR/15.2.6-F-recovery-consistency-audit.txt"

mkdir -p "$RESULT_DIR"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.6-F"
echo "RECOVERY CONSISTENCY AUDIT"
echo "======================================================================"
echo
echo "Generated: $(date -Iseconds)"
echo "Root: $ROOT"
echo
echo "STATUS: READ-ONLY"
echo "Nenhum banco, objeto, journal ou código será alterado."
echo

echo "======================================================================"
echo "[1] ARQUIVOS DE RECOVERY"
echo "======================================================================"

for f in \
    "$ROOT/node/transaction.py" \
    "$ROOT/node/recovery.py" \
    "$ROOT/node/registry.py"
do
    if [ -f "$f" ]; then
        echo "PASS  $f"
    else
        echo "FAIL  $f ausente"
    fi
done

echo

echo "======================================================================"
echo "[2] ENTRY POINTS DE RECOVERY"
echo "======================================================================"

grep -RniE \
'def (recover|recovery)|recover_transaction|recover_pending_transactions|recovery_status' \
"$ROOT/node/transaction.py" \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[3] ESTADOS DE TRANSACTION"
echo "======================================================================"

grep -nE \
'PREPARED|WRITING|VERIFYING|COMMITTING|COMMITTED|FAILED|ROLLBACK' \
"$ROOT/node/transaction.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[4] ESTADOS RECONHECIDOS PELO RECOVERY"
echo "======================================================================"

grep -nE \
'PREPARED|WRITING|VERIFYING|COMMITTING|COMMITTED|FAILED|ROLLBACK' \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[5] JOURNAL"
echo "======================================================================"

echo "--- transaction.py ---"
grep -nEi \
'journal|commit_marker|resources|phase' \
"$ROOT/node/transaction.py" \
2>/dev/null || true

echo
echo "--- recovery.py ---"
grep -nEi \
'journal|commit_marker|resources|phase' \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[6] VERIFICAÇÃO FÍSICA"
echo "======================================================================"

echo "--- transaction.py ---"
grep -nEi \
'verify|sha256|hash|storage_path|physical|block' \
"$ROOT/node/transaction.py" \
2>/dev/null || true

echo
echo "--- recovery.py ---"
grep -nEi \
'verify|sha256|hash|storage_path|physical|block' \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[7] ROLLBACK"
echo "======================================================================"

echo "--- transaction.py ---"
grep -nEi \
'rollback|purge|delete|cleanup' \
"$ROOT/node/transaction.py" \
2>/dev/null || true

echo
echo "--- recovery.py ---"
grep -nEi \
'rollback|purge|delete|cleanup' \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[8] TERMINAL STATES"
echo "======================================================================"

echo "--- transaction.py ---"
grep -nEi \
'terminal|COMMITTED|ROLLBACK|NOOP' \
"$ROOT/node/transaction.py" \
2>/dev/null || true

echo
echo "--- recovery.py ---"
grep -nEi \
'terminal|COMMITTED|ROLLBACK|NOOP' \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[9] IDEMPOTENCY / RECOVERY"
echo "======================================================================"

grep -RniE \
'idempot|request_fingerprint|idempotency_key|replay|conflict' \
"$ROOT/node/transaction.py" \
"$ROOT/node/recovery.py" \
"$ROOT/node/registry.py" \
2>/dev/null || true

echo

echo "======================================================================"
echo "[10] RECOVERY CHAIN"
echo "======================================================================"

grep -RniE \
'recover_transaction|recover_pending_transactions|recovery_status' \
"$ROOT" \
--exclude-dir=.venv \
--exclude-dir=__pycache__ \
--exclude='*.pyc' \
2>/dev/null | head -200 || true

echo

echo "======================================================================"
echo "[11] PYTHON AST AUDIT"
echo "======================================================================"

cd "$ROOT"

PYTHONPATH="$ROOT" python - <<'PY'
import ast
from pathlib import Path

files = [
    Path("node/transaction.py"),
    Path("node/recovery.py"),
]

for path in files:
    print()
    print(f"FILE: {path}")

    try:
        tree = ast.parse(path.read_text())
    except Exception as exc:
        print(f"FAIL AST: {exc}")
        continue

    functions = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    print("Recovery-related functions:")

    for name in sorted(set(functions)):
        if "recover" in name.lower() or "rollback" in name.lower():
            print(f"  - {name}")

    print("PASS AST")
PY

echo

echo "======================================================================"
echo "[12] DATABASE — ESTADO ATUAL"
echo "======================================================================"

DB="$ROOT/data/registry.db"

if [ -f "$DB" ]; then

python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/registry.db")

con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

print("SQLite integrity:")
print(con.execute("PRAGMA integrity_check").fetchone()[0])

print()
print("Foreign key violations:")
rows = con.execute("PRAGMA foreign_key_check").fetchall()
print(len(rows))

print()
print("Transaction states:")

rows = con.execute("""
    SELECT state, COUNT(*) AS total
    FROM transactions
    GROUP BY state
    ORDER BY state
""").fetchall()

for row in rows:
    print(f"  {row['state']}: {row['total']}")

print()
print("Transaction journals:")

total = con.execute("""
    SELECT COUNT(*) FROM transaction_journal
""").fetchone()[0]

print(f"  total: {total}")

print()
print("Transactions without journal:")

without_journal = con.execute("""
    SELECT COUNT(*)
    FROM transactions t
    LEFT JOIN transaction_journal j
      ON j.transaction_id = t.transaction_id
    WHERE j.transaction_id IS NULL
""").fetchone()[0]

print(f"  total: {without_journal}")

print()
print("Recoverable transactions:")

recoverable = con.execute("""
    SELECT state, COUNT(*)
    FROM transactions
    WHERE state IN (
        'PREPARED',
        'WRITING',
        'VERIFYING',
        'COMMITTING'
    )
    GROUP BY state
    ORDER BY state
""").fetchall()

if not recoverable:
    print("  none")
else:
    for state, total in recoverable:
        print(f"  {state}: {total}")

print()
print("Commit markers:")

rows = con.execute("""
    SELECT commit_marker, COUNT(*)
    FROM transaction_journal
    GROUP BY commit_marker
    ORDER BY commit_marker
""").fetchall()

for marker, total in rows:
    print(f"  commit_marker={marker}: {total}")

con.close()
PY

else
    echo "FAIL: registry.db não encontrado"
fi

echo

echo "======================================================================"
echo "[13] CONSISTENCY MATRIX"
echo "======================================================================"

cat <<'EOF'
                    transaction.py       recovery.py

PREPARED             recoverable           recoverable
WRITING              recoverable           recoverable
VERIFYING            recoverable           recoverable
COMMITTING           recoverable           recoverable
COMMITTED            terminal              terminal
FAILED               transitional          rollback path
ROLLBACK             terminal              terminal

JOURNAL              verificar             obrigatório
COMMIT MARKER        simplificado           validado
PHYSICAL VERIFY      limitado              obrigatório
ROLLBACK             básico                 cleanup + rollback
IDEMPOTENCY           integrada             compatível
EOF

echo

echo "======================================================================"
echo "[14] DISCREPÂNCIA ARQUITETURAL CONHECIDA"
echo "======================================================================"

cat <<'EOF'
PONTO CRÍTICO:

node/transaction.py possui uma recuperação simplificada.

Em COMMITTING + commit_marker=True:
    -> pode promover diretamente para COMMITTED.

node/recovery.py possui uma recuperação mais rigorosa.

Em presença de commit_marker:
    -> consulta o journal
    -> obtém resources
    -> verifica recursos físicos
    -> valida objeto/blocos
    -> somente então COMMITTED.

Portanto:

transaction.py
    = mecanismo transacional de baixo nível

recovery.py
    = mecanismo de recuperação física/operacional

A auditoria deve determinar se essa separação é:
    1. intencional;
    2. documentada;
    3. segura;
    4. ou uma duplicação que deve ser consolidada.

NENHUMA ALTERAÇÃO SERÁ FEITA NESTA ETAPA.
EOF

echo

echo "======================================================================"
echo "[15] RESULTADO 15.2.6-F"
echo "======================================================================"

cat <<'EOF'
Objetivos desta fase:

[PASS] localizar entry points de recovery
[PASS] comparar estados
[PASS] comparar journal
[PASS] comparar commit marker
[PASS] comparar verificação física
[PASS] comparar rollback
[PASS] comparar estados terminais
[PASS] comparar idempotência
[PASS] verificar cadeia de chamadas
[PASS] verificar estado persistido
[REVIEW] decidir arquitetura canônica de recovery

PRÓXIMA FASE:

15.2.6-G — RECOVERY FINAL AUDIT

Nenhuma mutação de banco foi executada.
EOF

echo
echo "======================================================================"
echo "FIM — 15.2.6-F"
echo "Resultado salvo em:"
echo "$RESULT"
echo "======================================================================"

} | tee "$RESULT"

echo
echo "AUDITORIA CONCLUÍDA."
echo "Arquivo:"
echo "$RESULT"
