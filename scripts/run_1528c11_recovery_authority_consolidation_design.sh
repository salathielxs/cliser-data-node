#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
OUT="$ROOT/tmp/15.2.8-C.11-recovery-authority-consolidation-design.txt"

mkdir -p "$ROOT/tmp"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-C.11"
echo "RECOVERY AUTHORITY CONSOLIDATION DESIGN FORENSIC"
echo "======================================================================"
echo
echo "OBJETIVO"
echo "Definir a arquitetura-alvo da autoridade de Recovery antes de qualquer"
echo "alteração de código."
echo
echo "REGRA: ZERO ALTERAÇÕES DE CÓDIGO."
echo

echo "======================================================================"
echo "[1] TRANSACTION.PY — ESTRUTURA COMPLETA"
echo "======================================================================"

nl -ba "$ROOT/node/transaction.py" 2>/dev/null || true

echo
echo "======================================================================"
echo "[2] RECOVERY.PY — ESTRUTURA COMPLETA"
echo "======================================================================"

nl -ba "$ROOT/node/recovery.py" 2>/dev/null || true

echo
echo "======================================================================"
echo "[3] TRANSACTION.PY — IMPORTS"
echo "======================================================================"

sed -n '1,80p' "$ROOT/node/transaction.py" 2>/dev/null || true

echo
echo "======================================================================"
echo "[4] RECOVERY.PY — IMPORTS"
echo "======================================================================"

sed -n '1,100p' "$ROOT/node/recovery.py" 2>/dev/null || true

echo
echo "======================================================================"
echo "[5] TRANSACTION STATE CONTRACT"
echo "======================================================================"

grep -nE \
'TransactionState|RECOVERABLE_STATES|TERMINAL|transition|def commit|def rollback|def fail|snapshot' \
"$ROOT/node/transaction.py" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[6] RECOVERY CONTRACT"
echo "======================================================================"

grep -nE \
'RECOVERABLE_STATES|def recover_|def _recover_|def _rollback_|def recovery_status|commit_marker|NOOP|ROLLBACK|COMMITTED' \
"$ROOT/node/recovery.py" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[7] OBJECT MANAGER — TRANSACTION BOUNDARY"
echo "======================================================================"

grep -nE \
'Transaction|TransactionState|create_transaction|update_transaction_state|create_transaction_journal|update_transaction_journal|commit_marker|recover' \
"$ROOT/node/object_manager.py" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[8] REGISTRY — TRANSACTION/JOURNAL CONTRACT"
echo "======================================================================"

grep -nE \
'def (create_transaction|update_transaction_state|create_transaction_journal|update_transaction_journal|get_transaction|get_transaction_journal|list_transactions)|transaction_journal|commit_marker' \
"$ROOT/node/registry.py" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[9] TESTS — TRANSACTION MODEL"
echo "======================================================================"

for f in \
"$ROOT/tests/test_transaction_failure_rollback.py" \
"$ROOT/tests/test_recovery_idempotency.py" \
"$ROOT/tests/test_transaction_recovery.py"
do
    if [ -f "$f" ]; then
        echo
        echo "--- $(basename "$f") ---"
        sed -n '1,260p' "$f"
    fi
done

echo
echo "======================================================================"
echo "[10] TESTS — RECOVERY AUTHORITY"
echo "======================================================================"

for f in \
"$ROOT/tests/test_atomicity.py" \
"$ROOT/tests/test_commit_marker.py" \
"$ROOT/tests/test_crash_recovery.py"
do
    if [ -f "$f" ]; then
        echo
        echo "--- $(basename "$f") ---"
        grep -n -A8 -B5 \
        -E 'from node\.(transaction|recovery)|recover_transaction|recover_pending_transactions|commit_marker|ROLLBACK|COMMITTED|NOOP' \
        "$f" 2>/dev/null || true
    fi
done

echo
echo "======================================================================"
echo "[11] TESTS — RESTART / FAULT INJECTION"
echo "======================================================================"

for f in \
"$ROOT/tests/test_persistent_restart_recovery.py" \
"$ROOT/tests/test_crash_recovery_fault_injection.py"
do
    if [ -f "$f" ]; then
        echo
        echo "--- $(basename "$f") ---"
        grep -n -A8 -B5 \
        -E 'TransactionProcessor|recovery|recover|journal|restart|crash|rollback|commit' \
        "$f" 2>/dev/null || true
    fi
done

echo
echo "======================================================================"
echo "[12] DOCUMENTAÇÃO — ARQUITETURA"
echo "======================================================================"

grep -n -A8 -B5 \
-E 'Transaction Model|Recovery Engine|recovery|transaction|commit marker|restart' \
"$ROOT/docs/architecture/ARCHITECTURE.md" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[13] DOCUMENTAÇÃO — TRANSACTION RECOVERY MODEL"
echo "======================================================================"

grep -n -A10 -B5 \
-E 'Recovery|recovery|Transaction|restart|commit marker|journal|rollback|COMMITTED' \
"$ROOT/docs/architecture/TRANSACTION_RECOVERY_MODEL.md" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[14] DOCUMENTAÇÃO — IMPLEMENTATION"
echo "======================================================================"

grep -n -A10 -B5 \
-E 'Recovery Engine|recovery|Transaction|rollback|commit|restart' \
"$ROOT/docs/architecture/TRANSACTION_RECOVERY_IMPLEMENTATION.md" \
2>/dev/null || true

echo
echo "======================================================================"
echo "[15] CONSUMIDORES DE TRANSACTION CLASS"
echo "======================================================================"

grep -RniE \
'from node\.transaction import.*Transaction|Transaction\(' \
"$ROOT/node" "$ROOT/api" "$ROOT/cli" "$ROOT/tests" \
--include='*.py' \
--exclude='transaction.py' \
2>/dev/null || true

echo
echo "======================================================================"
echo "[16] CONSUMIDORES DE TRANSACTIONSTATE"
echo "======================================================================"

grep -RniE \
'from node\.transaction import.*TransactionState|TransactionState\.' \
"$ROOT/node" "$ROOT/api" "$ROOT/cli" "$ROOT/tests" \
--include='*.py' \
--exclude='transaction.py' \
2>/dev/null || true

echo
echo "======================================================================"
echo "[17] CONSUMIDORES DE RECOVERY API"
echo "======================================================================"

grep -RniE \
'from node\.recovery import|import node\.recovery|recover_transaction\(|recover_pending_transactions\(|recovery_status\(' \
"$ROOT/node" "$ROOT/api" "$ROOT/cli" "$ROOT/scripts" "$ROOT/tests" \
--include='*.py' \
--exclude='recovery.py' \
2>/dev/null || true

echo
echo "======================================================================"
echo "[18] POSSÍVEIS RE-EXPORTS / ALIASES"
echo "======================================================================"

grep -RniE \
'transaction\.recover|recovery\.recover|recover_transaction[[:space:]]*=|recover_pending_transactions[[:space:]]*=' \
"$ROOT" \
--exclude-dir='.venv' \
--exclude-dir='__pycache__' \
--exclude='*.pyc' \
2>/dev/null || true

echo
echo "======================================================================"
echo "[19] FUTURO PONTO DE INTEGRAÇÃO DE STARTUP"
echo "======================================================================"

echo "--- api/app.py ---"
nl -ba "$ROOT/api/app.py" 2>/dev/null | sed -n '1,180p'

echo
echo "--- cli/main.py — ENTRYPOINT ---"
grep -n -A30 -B15 \
'if __name__ == "__main__"|def main' \
"$ROOT/cli/main.py" \
2>/dev/null || true

echo
echo "--- SERVER REFERENCES ---"
grep -RniE \
'uvicorn|api\.app|FastAPI\(' \
"$ROOT" \
--exclude-dir='.venv' \
--exclude-dir='__pycache__' \
--exclude='*.pyc' \
--exclude='*.log' \
2>/dev/null || true

echo
echo "======================================================================"
echo "[20] ARQUITETURA-ALVO — PROPOSTA FORENSE"
echo "======================================================================"

cat <<'EOF'
TARGET ARCHITECTURE

TRANSACTION MODEL
node/transaction.py

RESPONSABILIDADES:
- TransactionState
- Transaction
- state transitions
- lifecycle
- snapshot
- fail
- rollback
- commit

NÃO RESPONSÁVEL POR:
- recuperação física
- limpeza de objetos
- limpeza de manifests
- limpeza de blocos
- validação física de objetos
- recuperação automática de processo


PERSISTENCE
node/registry.py

RESPONSABILIDADES:
- transaction persistence
- journal persistence
- commit marker persistence
- transaction queries
- transaction state persistence


RECOVERY ENGINE
node/recovery.py

RESPONSABILIDADES:
- recover_transaction()
- recover_pending_transactions()
- recovery_status()
- journal inspection
- commit-marker interpretation
- persistent resource verification
- object validation
- manifest validation
- block validation
- rollback cleanup
- idempotent recovery


APPLICATION RUNTIME
api/app.py / future lifecycle

RESPONSABILIDADES FUTURAS:
- iniciar processo
- executar recovery pending
- somente depois liberar operação normal

IMPORTANT:
A integração de startup será uma etapa posterior.
A consolidação não deve introduzir startup recovery nesta etapa.
EOF

echo
echo "======================================================================"
echo "[21] IMPACT MATRIX"
echo "======================================================================"

cat <<'EOF'
COMPONENTE                    IMPACTO
----------------------------------------------------------------------
node/transaction.py           ALTO
node/recovery.py              MÉDIO
node/registry.py              BAIXO
node/object_manager.py        BAIXO
tests/test_atomicity.py       ALTO
tests/test_commit_marker.py   ALTO
tests/test_crash_recovery.py  BAIXO
tests/*transaction*            MÉDIO
scripts/g951_idempotency.py    BAIXO
scripts/g952_pending.py        BAIXO
api/app.py                     FUTURO
docs/architecture/*            MÉDIO
EOF

echo
echo "======================================================================"
echo "[22] DECISÕES QUE C.11 DEVE RESPONDER"
echo "======================================================================"

cat <<'EOF'
D1 — A autoridade única de recuperação será node.recovery?

D2 — TransactionState e Transaction permanecerão em node.transaction?

D3 — recover_transaction() será removido da API pública de node.transaction?

D4 — recover_pending_transactions() será removido da API pública de
     node.transaction?

D5 — Os testes que usam node.transaction para recovery serão migrados para
     node.recovery?

D6 — A semântica mais completa de node.recovery será preservada?

D7 — O commit-marker continuará sendo interpretado pelo Recovery Engine?

D8 — A recuperação continuará verificando recursos persistidos antes de
     confirmar COMMITTED?

D9 — O rollback continuará limpando manifest/object/block conforme as
     regras existentes?

D10 — Startup recovery será separado da consolidação?
EOF

echo
echo "======================================================================"
echo "[23] GIT STATUS"
echo "======================================================================"

git -C "$ROOT" status --short 2>/dev/null || true

echo
echo "======================================================================"
echo "15.2.8-C.11 — FIM"
echo "======================================================================"

} | tee "$OUT"

echo
echo "RELATÓRIO:"
echo "$OUT"
