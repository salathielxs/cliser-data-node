#!/data/data/com.termux/files/usr/bin/bash

set -u

NS="cliser-operational-auto"
QUOTA=10485760
DATA="CLISER DATA NODE — objeto operacional automático — $(date -Iseconds)"

echo "======================================================================"
echo "CLISER DATA NODE — OPERATIONAL SMOKE TEST"
echo "======================================================================"

echo
echo "[1] NAMESPACE"
python -m cli.main namespace create "$NS" "$QUOTA"

echo
echo "[2] QUOTA"
python - <<PY
from node.quota import get_quota, can_allocate_quota

ns = "$NS"

quota = get_quota(ns)
allocation = can_allocate_quota(100, namespace=ns)

print("Quota:", quota)
print("Allocation:", allocation)

if quota is None:
    raise SystemExit("FAIL: quota não encontrada")

if not allocation.get("allowed"):
    raise SystemExit(
        f"FAIL: allocation bloqueada: {allocation}"
    )
PY

echo
echo "[3] PUT"
PUT_OUTPUT=$(python -m cli.main put "$DATA" "$NS")
printf '%s\n' "$PUT_OUTPUT"

OBJECT_ID=$(printf '%s\n' "$PUT_OUTPUT" |
    sed -n 's/^Object ID:[[:space:]]*//p' |
    head -n 1)

if [ -z "$OBJECT_ID" ]; then
    echo "FAIL: Object ID não encontrado."
    exit 1
fi

echo
echo "OBJECT_ID=$OBJECT_ID"

echo
echo "[4] GET"
python -m cli.main get "$OBJECT_ID"

echo
echo "[5] INSPECT"
python -m cli.main inspect "$OBJECT_ID"

echo
echo "[6] VERIFY"
VERIFY_OUTPUT=$(python -m cli.main verify "$OBJECT_ID")
printf '%s\n' "$VERIFY_OUTPUT"

if ! printf '%s\n' "$VERIFY_OUTPUT" | grep -q "Integrity: OK"; then
    echo "FAIL: integridade não confirmada."
    exit 1
fi

echo
echo "[7] OBJECT REGISTRY"
python -m cli.main objects "$NS"

echo
echo "[8] NAMESPACE METRICS"
python -m cli.main metrics namespace "$NS"

echo
echo "======================================================================"
echo "OPERATIONAL SMOKE TEST: PASS"
echo "======================================================================"
echo "Namespace: $NS"
echo "Object ID: $OBJECT_ID"
echo "Quota:     $QUOTA bytes"
echo "======================================================================"
