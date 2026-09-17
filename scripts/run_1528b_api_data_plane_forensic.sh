#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
OUT="$ROOT/tmp/15.2.8-B-api-data-plane-forensic.txt"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-B API / DATA PLANE BOUNDARY FORENSIC"
echo "======================================================================"

echo
echo "[1] API LAYER FILES"
find "$ROOT/api" \
  -type f \
  -name '*.py' \
  ! -path '*/__pycache__/*' \
  | sort

echo
echo "[2] API → SERVICE IMPORTS"
grep -RniE \
  'from api\.services|import api\.services|from node\.|import node\.' \
  "$ROOT/api" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1000

echo
echo "[3] API DIRECT DATABASE ACCESS"
grep -RniE \
  'sqlite3|sqlite|connect\(|cursor\(|execute\(|executemany\(|executescript\(' \
  "$ROOT/api" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1000

echo
echo "[4] API DIRECT PHYSICAL STORAGE ACCESS"
grep -RniE \
  'open\(|write_bytes|write_text|read_bytes|read_text|unlink\(|rename\(|mkdir\(|OBJECTS_DIR|BLOCKS_DIR|STORAGE_DIR|Path\(' \
  "$ROOT/api" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1000

echo
echo "[5] SERVICE → NODE CORE"
grep -RniE \
  'from node\.|import node\.|object_manager|registry|transaction|storage|manifest|block' \
  "$ROOT/api/services" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1000

echo
echo "[6] NODE CORE STORAGE ACCESS"
grep -RniE \
  'sqlite3|connect\(|execute\(|executemany\(|open\(|write_bytes|write_text|read_bytes|read_text|unlink\(|rename\(|mkdir\(' \
  "$ROOT/node" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1500

echo
echo "[7] OBJECT WRITE PATH"
grep -RniE \
  'put_object|create_object|register_object|create_manifest|allocate|write_bytes|OBJECTS_DIR|BLOCKS_DIR' \
  "$ROOT/api" "$ROOT/node" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1200

echo
echo "[8] TRANSACTION ENTRY PATH"
grep -RniE \
  'create_transaction|create_idempotent_transaction|Transaction\(|create_transaction_journal|update_transaction_state|commit|rollback|recover' \
  "$ROOT/api" "$ROOT/node" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null | head -1500

echo
echo "[9] API ROUTE → SERVICE → NODE TRACE"
for f in "$ROOT"/api/routes/*.py; do
    [ -f "$f" ] || continue

    echo
    echo "--- ROUTE: $(basename "$f") ---"

    grep -nE \
      'def |async def |service|manager|node\.|put_object|delete_object|get_object|transaction|namespace|storage' \
      "$f" \
      2>/dev/null | head -250
done

echo
echo "[10] POSSIBLE BYPASS CANDIDATES"

BYPASS_COUNT=$(
grep -RniE \
  'sqlite3|connect\(|cursor\(|execute\(|open\(|write_bytes|write_text|unlink\(' \
  "$ROOT/api" \
  --include='*.py' \
  --exclude='*.pyc' \
  2>/dev/null \
  | wc -l
)

echo "API_DIRECT_STORAGE_MATCHES=$BYPASS_COUNT"

if [ "$BYPASS_COUNT" -eq 0 ]; then
    echo "RESULT=PASS — API sem acesso direto identificado ao storage"
else
    echo "RESULT=REVIEW — existem referências que precisam de classificação"
fi

echo
echo "[11] ARCHITECTURE BRIDGE REFERENCES"

grep -nEi \
  'API Layer|Data Plane|Node Core|Persistent Storage|boundary|bypass|service' \
  "$ROOT/docs/architecture/ARCHITECTURE_BRIDGE_15_2_8.md" \
  2>/dev/null | head -500

echo
echo "======================================================================"
echo "15.2.8-B API / DATA PLANE FORENSIC COMPLETE"
echo "======================================================================"

} | tee "$OUT"

echo
echo "REPORT: $OUT"
