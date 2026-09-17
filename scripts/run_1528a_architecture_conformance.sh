#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
OUT="$ROOT/tmp/15.2.8-A-architecture-conformance.txt"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.8-A ARCHITECTURE CONFORMANCE FORENSIC"
echo "======================================================================"

echo
echo "[1] PROJECT STRUCTURE"
find "$ROOT" \
  -maxdepth 3 \
  -type f \
  \( -name '*.py' -o -name '*.md' \) \
  ! -path '*/.git/*' \
  ! -path '*/.venv/*' \
  | sort | head -500

echo
echo "[2] FASTAPI / API IMPLEMENTATION"
grep -RniE \
  'FastAPI|APIRouter|@app\.|@router\.|include_router|HTTPException|Request' \
  "$ROOT" \
  --include='*.py' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null | head -500

echo
echo "[3] CONTROL / MANAGEMENT REFERENCES"
grep -RniE \
  'control.?plane|management|administr|configuration|policy|quota|lifecycle|maintenance|operational' \
  "$ROOT" \
  --include='*.py' \
  --exclude='*.pyc' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null | head -500

echo
echo "[4] NODE CORE REFERENCES"
grep -RniE \
  'transaction|registry|storage|object|manifest|block|namespace|recovery|integrity|journal' \
  "$ROOT" \
  --include='*.py' \
  --exclude='*.pyc' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null | head -700

echo
echo "[5] DIRECT STORAGE ACCESS"
grep -RniE \
  'sqlite3|connect\(|open\(|Path\(|write_bytes|write_text|unlink\(|rename\(|mkdir\(' \
  "$ROOT" \
  --include='*.py' \
  --exclude='*.pyc' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null | head -700

echo
echo "[6] TRANSACTION REFERENCES"
grep -RniE \
  'transaction|begin|commit|rollback|journal|recovery|idempot' \
  "$ROOT" \
  --include='*.py' \
  --exclude='*.pyc' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null | head -700

echo
echo "[7] SECURITY REFERENCES"
grep -RniE \
  'auth|authentication|authorization|credential|permission|identity|token|namespace' \
  "$ROOT" \
  --include='*.py' \
  --exclude='*.pyc' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null | head -700

echo
echo "[8] POSSIBLE API → STORAGE BYPASS"
grep -RniE \
  'sqlite3|open\(|write_bytes|write_text|unlink\(' \
  "$ROOT" \
  --include='*.py' \
  --exclude='*.pyc' \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  2>/dev/null \
  | grep -Ei 'api|route|router|endpoint|http|main|app' \
  | head -300

echo
echo "[9] ARCHITECTURE DOCUMENT"
grep -nEi \
  'Control Plane|API Layer|Data Plane|Node Core|Persistent Storage|Transaction Boundary|Security Boundary' \
  "$ROOT/docs/architecture/ARCHITECTURE_BRIDGE_15_2_8.md" \
  2>/dev/null

echo
echo "======================================================================"
echo "15.2.8-A ARCHITECTURE CONFORMANCE FORENSIC COMPLETE"
echo "======================================================================"

} | tee "$OUT"

echo
echo "REPORT: $OUT"
