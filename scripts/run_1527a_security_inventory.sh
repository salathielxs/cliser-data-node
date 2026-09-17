#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
OUT="$ROOT/tmp/15.2.7-A-security-inventory.txt"

mkdir -p "$ROOT/tmp"

{
echo "======================================================================"
echo "CLISER DATA NODE — 15.2.7-A SECURITY ARCHITECTURE INVENTORY"
echo "======================================================================"
echo
echo "Generated: $(date -Iseconds)"
echo

echo "[1] SECURITY FILES"
echo "----------------------------------------------------------------------"
find "$ROOT/api" "$ROOT/node" "$ROOT/cli" "$ROOT/scripts" \
  -type f \
  \( -iname '*auth*' \
     -o -iname '*security*' \
     -o -iname '*credential*' \
     -o -iname '*identity*' \
     -o -iname '*crypto*' \
     -o -iname '*permission*' \
     -o -iname '*access*' \
     -o -iname '*token*' \
  \) \
  -not -path '*/__pycache__/*' \
  -not -name '*.pyc' \
  | sort

echo
echo "[2] AUTHENTICATION REFERENCES"
echo "----------------------------------------------------------------------"
grep -RniE \
  'authentication|authenticated|bearer|authorization|token|credential' \
  "$ROOT/api" "$ROOT/node" "$ROOT/cli" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[3] AUTHORIZATION / RBAC"
echo "----------------------------------------------------------------------"
grep -RniE \
  'role|permission|authorize|authorization|access_control|RBAC|ADMIN|WRITER|READER' \
  "$ROOT/api" "$ROOT/node" "$ROOT/cli" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[4] IDENTITY"
echo "----------------------------------------------------------------------"
grep -RniE \
  'identity|identity_id|principal|crypto_identity' \
  "$ROOT/api" "$ROOT/node" "$ROOT/cli" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[5] CREDENTIALS / TOKEN STORAGE"
echo "----------------------------------------------------------------------"
grep -RniE \
  'api_credentials|token_hash|credential_id|secret|password|key_hash' \
  "$ROOT/api" "$ROOT/node" "$ROOT/cli" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[6] CRYPTOGRAPHY"
echo "----------------------------------------------------------------------"
grep -RniE \
  'cryptography|hashlib|sha256|sha512|hmac|fernet|AES|RSA|Ed25519|signature|sign|verify' \
  "$ROOT/api" "$ROOT/node" "$ROOT/cli" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[7] NAMESPACE SECURITY"
echo "----------------------------------------------------------------------"
grep -RniE \
  'namespace|namespace_security|namespace_manager|isolation|tenant' \
  "$ROOT/api" "$ROOT/node" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[8] OBJECT / STORAGE ACCESS CONTROL"
echo "----------------------------------------------------------------------"
grep -RniE \
  'object_manager|storage|block_manager|access|permission|namespace' \
  "$ROOT/api/routes" "$ROOT/node" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[9] SECURITY MIDDLEWARE"
echo "----------------------------------------------------------------------"
find "$ROOT/api" -type f \
  -not -path '*/__pycache__/*' \
  -not -name '*.pyc' \
  -print \
  | sort

echo
echo "Middleware references:"
grep -RniE \
  'middleware|Security|Depends|HTTPBearer|Authorization' \
  "$ROOT/api" \
  --exclude-dir=__pycache__ \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[10] SECURITY CONFIGURATION"
echo "----------------------------------------------------------------------"
grep -RniE \
  'SECURITY|AUTH|TOKEN|CREDENTIAL|MAX_|SECRET|KEY' \
  "$ROOT/api/config.py" "$ROOT/config" \
  --exclude='*.pyc' \
  2>/dev/null || true

echo
echo "[11] DATABASE SECURITY STRUCTURE"
echo "----------------------------------------------------------------------"
python - <<'PY'
import sqlite3

db = "data/registry.db"

conn = sqlite3.connect(db)
conn.execute("PRAGMA foreign_keys = ON")

print("Tables:")
for row in conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
"""):
    print(" ", row[0])

print()
print("Security-related tables:")
for row in conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type='table'
      AND (
        lower(name) LIKE '%credential%'
        OR lower(name) LIKE '%identity%'
        OR lower(name) LIKE '%permission%'
        OR lower(name) LIKE '%auth%'
        OR lower(name) LIKE '%security%'
      )
    ORDER BY name
"""):
    print(" ", row[0])

print()
print("api_credentials schema:")
try:
    for row in conn.execute("PRAGMA table_info(api_credentials)"):
        print(row)
except Exception as e:
    print("ERROR:", e)

conn.close()
PY

echo
echo "[12] POTENTIAL SECRET MATERIAL — FILENAMES ONLY"
echo "----------------------------------------------------------------------"
find "$ROOT" -type f \
  \( -iname '*.pem' \
     -o -iname '*.key' \
     -o -iname '*.crt' \
     -o -iname '*secret*' \
     -o -iname '*credential*' \
  \) \
  -not -path '*/__pycache__/*' \
  -not -name '*.pyc' \
  2>/dev/null \
  | sort

echo
echo "[13] SECURITY TESTS"
echo "----------------------------------------------------------------------"
find "$ROOT/tests" -type f \
  \( -iname '*auth*' \
     -o -iname '*security*' \
     -o -iname '*credential*' \
     -o -iname '*identity*' \
     -o -iname '*permission*' \
     -o -iname '*access*' \
  \) \
  -not -path '*/__pycache__/*' \
  -not -name '*.pyc' \
  | sort

echo
echo "[14] SECURITY DOCUMENTATION"
echo "----------------------------------------------------------------------"
find "$ROOT/docs" -type f \
  -not -path '*/__pycache__/*' \
  -not -name '*.pyc' \
  | grep -Ei 'security|auth|identity|credential|access|permission' \
  | sort || true

echo
echo "======================================================================"
echo "15.2.7-A INVENTORY COMPLETE"
echo "======================================================================"
echo
echo "OUTPUT: $OUT"

} | tee "$OUT"
