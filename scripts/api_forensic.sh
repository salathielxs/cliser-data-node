#!/data/data/com.termux/files/usr/bin/bash

set +e

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

FORENSIC_DIR="$ROOT/reports/forensic"
mkdir -p "$FORENSIC_DIR"
REPORT="$FORENSIC_DIR/api_forensic_$(date +%Y%m%d_%H%M%S).log"
HEALTH_JSON="$FORENSIC_DIR/.health.json"
HEALTH_ERR="$FORENSIC_DIR/.health.err"

echo "======================================================================"
echo "CLISER DATA NODE — API FORENSIC ISOLATION"
echo "======================================================================"
echo
echo "DATE: $(date)"
echo "ROOT: $ROOT"
echo

{
    echo "======================================================================"
    echo "[1] SERVER / HEALTH"
    echo "======================================================================"

    if curl -fsS --max-time 5 \
        http://127.0.0.1:8000/api/v1/health \
        > "$HEALTH_JSON" 2>"$HEALTH_ERR"
    then
        echo "HEALTH: PASS"
        cat "$HEALTH_JSON"
    else
        echo "HEALTH: FAIL"
        cat "$HEALTH_ERR"
    fi

    echo
    echo "======================================================================"
    echo "[2] API TEST FILES"
    echo "======================================================================"

    find tests/api -maxdepth 1 -type f -name 'test_*.py' | sort

    echo
    echo "======================================================================"
    echo "[3] FULL API TEST SUITE"
    echo "======================================================================"

    pytest -q tests/api --tb=short --maxfail=0

    PYTEST_RC=$?

    echo
    echo "======================================================================"
    echo "[4] PYTEST RESULT"
    echo "======================================================================"

    echo "PYTEST_EXIT_CODE=$PYTEST_RC"

    if [ "$PYTEST_RC" -eq 0 ]; then
        echo "STATUS=PASS"
    else
        echo "STATUS=FAIL"
    fi

    echo
    echo "======================================================================"
    echo "[5] WARNING AUDIT"
    echo "======================================================================"

    echo "Known dependency warning:"
    echo "starlette.formparsers.py:"
    echo "PendingDeprecationWarning: Please use python_multipart instead."

    echo
    echo "======================================================================"
    echo "FORENSIC END"
    echo "======================================================================"

    exit "$PYTEST_RC"

} 2>&1 | tee "$REPORT"

# Recupera o resultado real do pytest através do relatório.
if grep -q '^PYTEST_EXIT_CODE=0$' "$REPORT"; then
    FINAL_RC=0
else
    FINAL_RC=1
fi

echo
echo "======================================================================"
echo "FORENSIC REPORT"
echo "======================================================================"
echo "$REPORT"
echo "FINAL_EXIT_CODE=$FINAL_RC"

exit "$FINAL_RC"
