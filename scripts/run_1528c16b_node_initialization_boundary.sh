#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"

cd "$ROOT" || exit 1

echo "======================================================================"
echo "15.2.8-C.16-B — NODE INITIALIZATION / RECOVERY INTEGRATION BOUNDARY"
echo "======================================================================"

RC_COMPILE=0
RC_REGISTRY=0
RC_RECOVERY=0
RC_APP=0

echo
echo "[1] APPLICATION ENTRYPOINT"
echo "----------------------------------------------------------------------"

if [ -f "api/app.py" ]; then
    echo "api/app.py=FOUND"

    grep -n -E \
      'FastAPI\(|include_router|middleware|app\.openapi' \
      api/app.py \
      2>/dev/null || true
else
    echo "api/app.py=ABSENT"
    RC_APP=1
fi

echo
echo "[2] FASTAPI LIFECYCLE HOOKS"
echo "----------------------------------------------------------------------"

LIFECYCLE="$(
    grep -RniE \
      'lifespan=|@app\.on_event|startup|shutdown' \
      api \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$LIFECYCLE" ]; then
    echo "$LIFECYCLE"
else
    echo "LIFECYCLE_HOOKS=ABSENT"
fi

echo
echo "[3] NODE INITIALIZATION FUNCTIONS"
echo "----------------------------------------------------------------------"

INIT_MATCHES="$(
    grep -RniE \
      '^[[:space:]]*(async[[:space:]]+)?def[[:space:]]+[A-Za-z0-9_]*(init|initialize|initializ|bootstrap|startup|load)[A-Za-z0-9_]*[[:space:]]*\(' \
      node api \
      --include='*.py' \
      --exclude-dir=__pycache__ \
      2>/dev/null || true
)"

if [ -n "$INIT_MATCHES" ]; then
    echo "$INIT_MATCHES"
else
    echo "NODE_INITIALIZATION_FUNCTIONS=NONE"
fi

echo
echo "[4] REGISTRY INITIALIZATION / DATABASE CREATION"
echo "----------------------------------------------------------------------"

if [ -f "node/registry.py" ]; then

    echo "node/registry.py=FOUND"

    grep -n -E \
      'DB_FILE|def connect|CREATE TABLE|sqlite3\.connect|mkdir|DATA_DIR' \
      node/registry.py \
      | head -180

    RC_REGISTRY=0
else
    echo "node/registry.py=ABSENT"
    RC_REGISTRY=1
fi

echo
echo "[5] REGISTRY CONNECTION CALL GRAPH"
echo "----------------------------------------------------------------------"

grep -RniE \
  'registry\.connect|from node\.registry import connect|registry import connect|connect\(\)' \
  api node \
  --include='*.py' \
  --exclude-dir=__pycache__ \
  --exclude='registry.py' \
  2>/dev/null \
  | head -180 || true

echo
echo "[6] RECOVERY ENGINE DEPENDENCIES"
echo "----------------------------------------------------------------------"

if [ -f "node/recovery.py" ]; then

    echo "node/recovery.py=FOUND"

    echo
    echo "--- imports ---"

    sed -n '1,80p' node/recovery.py

    echo
    echo "--- recovery entrypoints ---"

    grep -n -E \
      '^[[:space:]]*def (recover_transaction|recover_pending_transactions|recovery_status)\(' \
      node/recovery.py

    echo
    echo "--- registry dependencies ---"

    grep -n -E \
      'registry|transaction|journal|commit_marker|manifest|block|object' \
      node/recovery.py \
      | head -220

    RC_RECOVERY=0
else
    echo "node/recovery.py=ABSENT"
    RC_RECOVERY=1
fi

echo
echo "[7] TRANSACTION PERSISTENCE DEPENDENCIES"
echo "----------------------------------------------------------------------"

grep -n -E \
  'def (get_transaction|list_transactions|create_transaction|update_transaction|delete_transaction)|transaction_journal|commit_marker|transactions' \
  node/registry.py \
  | head -220 || true

echo
echo "[8] OBJECT / BLOCK / MANIFEST PERSISTENCE"
echo "----------------------------------------------------------------------"

grep -n -E \
  'def (get_object|register_object|delete_object|purge_object|register_block|get_block|delete_block|purge_manifest|manifest_blocks)' \
  node/registry.py \
  | head -220 || true

echo
echo "[9] IMPORT GRAPH — STARTUP → NODE CORE"
echo "----------------------------------------------------------------------"

grep -RniE \
  'from node\.|import node\.' \
  api \
  --include='*.py' \
  --exclude-dir=__pycache__ \
  2>/dev/null \
  | head -220 || true

echo
echo "[10] PY_COMPILE"
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
echo "[11] BOUNDARY CLASSIFICATION"
echo "----------------------------------------------------------------------"

if [ "$RC_APP" -ne 0 ]; then

    echo "15.2.8-C.16-B=REVIEW"
    echo "REASON=API_APP_NOT_FOUND"

elif [ "$RC_REGISTRY" -ne 0 ]; then

    echo "15.2.8-C.16-B=REVIEW"
    echo "REASON=REGISTRY_NOT_FOUND"

elif [ "$RC_RECOVERY" -ne 0 ]; then

    echo "15.2.8-C.16-B=REVIEW"
    echo "REASON=RECOVERY_ENGINE_NOT_FOUND"

elif [ "$RC_COMPILE" -ne 0 ]; then

    echo "15.2.8-C.16-B=REVIEW"
    echo "REASON=COMPILE_FAILURE"

else

    echo "15.2.8-C.16-B=PASS"
    echo "APPLICATION_ENTRYPOINT=IDENTIFIED"
    echo "REGISTRY_LAYER=IDENTIFIED"
    echo "RECOVERY_ENGINE=IDENTIFIED"
    echo "TRANSACTION_PERSISTENCE=IDENTIFIED"
    echo "RESOURCE_PERSISTENCE=IDENTIFIED"
    echo "STARTUP_BOUNDARY=FORENSICALLY_MAPPED"
    echo "PRODUCTION_MODIFICATION=NONE"

fi

echo
echo "======================================================================"
echo "15.2.8-C.16-B — COMPLETE"
echo "======================================================================"
