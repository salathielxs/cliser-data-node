#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.16-A — STARTUP RECOVERY FORENSIC GATE"
echo "======================================================================"

RC_APP=0
RC_STARTUP=0
RC_RECOVERY_CALL=0
RC_NODE_INIT=0
RC_IMPORTS=0
RC_COMPILE=0

echo
echo "[1] APPLICATION ENTRYPOINT"
echo "----------------------------------------------------------------------"

if [ -f "api/app.py" ]; then
    echo "api/app.py=FOUND"

    grep -n -E \
      'FastAPI|lifespan|startup|shutdown|on_event|include_router|create_app' \
      api/app.py \
      2>/dev/null || true

    RC_APP=0
else
    echo "api/app.py=ABSENT"
    RC_APP=1
fi

echo
echo "[2] STARTUP / LIFESPAN DEFINITIONS"
echo "----------------------------------------------------------------------"

STARTUP_MATCHES="$(
    grep -RniE \
      '^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+(lifespan|startup|shutdown)|@app\.(on_event|startup|shutdown)|lifespan=' \
      api node \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$STARTUP_MATCHES" ]; then
    echo "$STARTUP_MATCHES"
    RC_STARTUP=0
else
    echo "STARTUP_LIFESPAN_DEFINITIONS=ABSENT"
    RC_STARTUP=0
fi

echo
echo "[3] RECOVERY CALLS DURING STARTUP"
echo "----------------------------------------------------------------------"

STARTUP_RECOVERY="$(
    grep -RniE \
      'recover_pending_transactions|recover_transaction|recovery_status' \
      api node \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$STARTUP_RECOVERY" ]; then
    echo "$STARTUP_RECOVERY"
else
    echo "RECOVERY_CALLS_FOUND=NONE"
fi

echo
echo "[4] RECOVERY IMPORTS"
echo "----------------------------------------------------------------------"

RECOVERY_IMPORTS="$(
    grep -RniE \
      'from node\.recovery import|import node\.recovery' \
      api node \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$RECOVERY_IMPORTS" ]; then
    echo "$RECOVERY_IMPORTS"
else
    echo "RECOVERY_IMPORTS_FOUND=NONE"
fi

echo
echo "[5] NODE INITIALIZATION"
echo "----------------------------------------------------------------------"

NODE_INIT="$(
    grep -RniE \
      'initialize|initializ|bootstrap|startup|load|registry|database|sqlite|create.*table|init.*db' \
      api node \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$NODE_INIT" ]; then
    echo "$NODE_INIT" | head -150
    RC_NODE_INIT=0
else
    echo "NODE_INITIALIZATION_REFERENCES=NONE"
    RC_NODE_INIT=1
fi

echo
echo "[6] FASTAPI APP CONSTRUCTION"
echo "----------------------------------------------------------------------"

if [ -f "api/app.py" ]; then
    sed -n '1,240p' api/app.py
else
    echo "api/app.py unavailable"
fi

echo
echo "[7] RECOVERY ENGINE ENTRYPOINTS"
echo "----------------------------------------------------------------------"

grep -n -E \
  '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
  node/recovery.py

echo
echo "[8] TRANSACTION PERSISTENCE"
echo "----------------------------------------------------------------------"

grep -n -E \
  'transaction|journal|commit_marker|state' \
  node/registry.py \
  | head -120

echo
echo "[9] PY_COMPILE"
echo "----------------------------------------------------------------------"

python -m py_compile \
    api/app.py \
    node/transaction.py \
    node/recovery.py \
    node/object_manager.py \
    node/registry.py

RC_COMPILE=$?

echo "PY_COMPILE_RC=$RC_COMPILE"

echo
echo "[10] FINAL CLASSIFICATION"
echo "----------------------------------------------------------------------"

if [ "$RC_APP" -ne 0 ]; then

    echo "15.2.8-C.16-A=REVIEW"
    echo "REASON=API_APP_NOT_FOUND"

elif [ "$RC_COMPILE" -ne 0 ]; then

    echo "15.2.8-C.16-A=REVIEW"
    echo "REASON=COMPILE_FAILURE"

elif [ -n "$STARTUP_RECOVERY" ]; then

    echo "15.2.8-C.16-A=REVIEW"
    echo "REASON=STARTUP_RECOVERY_REFERENCE_FOUND"
    echo "STARTUP_INTEGRATION=DETECTED"

else

    echo "15.2.8-C.16-A=PASS"
    echo "STARTUP_RECOVERY=NOT_INTEGRATED"
    echo "RECOVERY_ENGINE=AVAILABLE"
    echo "RUNTIME_INTEGRATION=NOT_PRESENT"
    echo "NO_PRODUCTION_MODIFICATION=TRUE"
fi

echo
echo "======================================================================"
echo "15.2.8-C.16-A — COMPLETE"
echo "======================================================================"
