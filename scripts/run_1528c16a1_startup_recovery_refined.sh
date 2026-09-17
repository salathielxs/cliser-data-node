#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.16-A.1 — REFINED STARTUP RECOVERY FORENSIC"
echo "======================================================================"

RC=0

echo
echo "[1] FASTAPI APPLICATION CONSTRUCTION"
echo "----------------------------------------------------------------------"

grep -n -E \
  'FastAPI\(|lifespan=|on_event|include_router' \
  api/app.py \
  2>/dev/null || true

echo
echo "[2] REAL STARTUP / LIFESPAN DEFINITIONS"
echo "----------------------------------------------------------------------"

grep -RniE \
  '^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+(lifespan|startup|shutdown)\b|@app\.(on_event|startup|shutdown)|lifespan=' \
  api \
  --include='*.py' \
  --exclude-dir=__pycache__ \
  2>/dev/null || true

echo
echo "[3] RECOVERY REFERENCES OUTSIDE RECOVERY ENGINE"
echo "----------------------------------------------------------------------"

RECOVERY_EXTERNAL="$(
  grep -RniE \
    'recover_pending_transactions|recover_transaction|recovery_status' \
    api node \
    --include='*.py' \
    --exclude-dir=__pycache__ \
    --exclude='recovery.py' \
    2>/dev/null || true
)"

if [ -n "$RECOVERY_EXTERNAL" ]; then
    echo "$RECOVERY_EXTERNAL"
else
    echo "EXTERNAL_RECOVERY_REFERENCES=NONE"
fi

echo
echo "[4] RECOVERY IMPORTS OUTSIDE RECOVERY ENGINE"
echo "----------------------------------------------------------------------"

RECOVERY_IMPORTS="$(
  grep -RniE \
    'from node\.recovery import|import node\.recovery' \
    api node \
    --include='*.py' \
    --exclude-dir=__pycache__ \
    --exclude='recovery.py' \
    2>/dev/null || true
)"

if [ -n "$RECOVERY_IMPORTS" ]; then
    echo "$RECOVERY_IMPORTS"
else
    echo "EXTERNAL_RECOVERY_IMPORTS=NONE"
fi

echo
echo "[5] STARTUP REFERENCES IN APPLICATION"
echo "----------------------------------------------------------------------"

grep -RniE \
  'startup|lifespan|bootstrap|initialize|initializ' \
  api \
  --include='*.py' \
  --exclude-dir=__pycache__ \
  2>/dev/null || true

echo
echo "[6] APPLICATION IMPORT GRAPH — RECOVERY"
echo "----------------------------------------------------------------------"

grep -RniE \
  'node\.recovery|recover_pending_transactions|recover_transaction|recovery_status' \
  api \
  --include='*.py' \
  --exclude-dir=__pycache__ \
  2>/dev/null || true

echo
echo "[7] RECOVERY ENGINE DEFINITIONS — REFERENCE ONLY"
echo "----------------------------------------------------------------------"

grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
  node/recovery.py \
  2>/dev/null || true

echo
echo "[8] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
    api/app.py \
    node/transaction.py \
    node/recovery.py \
    node/object_manager.py \
    node/registry.py

COMPILE_RC=$?

echo "PY_COMPILE_RC=$COMPILE_RC"

echo
echo "[9] FINAL FORENSIC CLASSIFICATION"
echo "----------------------------------------------------------------------"

if [ "$COMPILE_RC" -ne 0 ]; then

    echo "15.2.8-C.16-A.1=REVIEW"
    echo "REASON=COMPILE_FAILURE"
    RC=1

elif [ -n "$RECOVERY_EXTERNAL" ] || [ -n "$RECOVERY_IMPORTS" ]; then

    echo "15.2.8-C.16-A.1=REVIEW"
    echo "REASON=EXTERNAL_RECOVERY_REFERENCE_FOUND"
    echo "STARTUP_INTEGRATION=REQUIRES_MANUAL_AUDIT"
    RC=1

else

    echo "15.2.8-C.16-A.1=PASS"
    echo "STARTUP_RECOVERY=NOT_INTEGRATED"
    echo "RECOVERY_ENGINE=AVAILABLE"
    echo "EXTERNAL_RECOVERY_REFERENCES=NONE"
    echo "RUNTIME_STARTUP_INTEGRATION=NOT_PRESENT"
    echo "PRODUCTION_MODIFICATION=NONE"

fi

echo
echo "======================================================================"
echo "15.2.8-C.16-A.1 — COMPLETE"
echo "======================================================================"

exit "$RC"
