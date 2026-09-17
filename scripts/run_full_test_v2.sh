#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

PASS=0
FAIL=0
SKIP=0
WARN=0

run_pytest() {
    local NAME="$1"
    shift

    echo
    echo "======================================================================"
    echo "$NAME"
    echo "======================================================================"

    OUTPUT=$(mktemp)

    python -m pytest -q "$@" >"$OUTPUT" 2>&1
    RC=$?

    cat "$OUTPUT"

    if [ "$RC" -eq 0 ]; then
        echo "[PASS] $NAME"
        PASS=$((PASS + 1))

    elif grep -q "no tests ran" "$OUTPUT"; then
        echo "[SKIP] $NAME — nenhum teste pytest detectado"
        SKIP=$((SKIP + 1))

    else
        echo "[FAIL] $NAME"
        FAIL=$((FAIL + 1))
    fi

    rm -f "$OUTPUT"
}

echo "======================================================================"
echo "       CLISER DATA NODE — FULL AUTOMATED TEST V2"
echo "======================================================================"

echo
echo "ROOT: $ROOT"
echo "DATE: $(date)"

echo
echo "======================================================================"
echo "[1] GIT STATE"
echo "======================================================================"

git branch --show-current
git log -5 --oneline --decorate
git status --short

echo
echo "======================================================================"
echo "[2] PYTHON"
echo "======================================================================"

python --version
python -c 'import sys; print("Executable:", sys.executable)'
python -c 'import platform; print("Platform:", platform.platform())'

echo
echo "======================================================================"
echo "[3] PYTHON COMPILE"
echo "======================================================================"

if python -m compileall -q api node cli scripts tests; then
    echo "[PASS] Python compilation"
    PASS=$((PASS + 1))
else
    echo "[FAIL] Python compilation"
    FAIL=$((FAIL + 1))
fi

echo
echo "======================================================================"
echo "[4] PYTEST"
echo "======================================================================"

if python -m pytest --version; then
    echo "[PASS] pytest disponível"
    PASS=$((PASS + 1))
else
    echo "[FAIL] pytest indisponível"
    FAIL=$((FAIL + 1))
fi

echo
echo "======================================================================"
echo "[5] OFFICIAL TEST SUITE — tests/"
echo "======================================================================"

run_pytest \
    "[5] OFFICIAL TEST SUITE" \
    tests/

echo
echo "======================================================================"
echo "[6] TRANSACTION / RECOVERY"
echo "======================================================================"

run_pytest \
    "[6] TRANSACTION RECOVERY" \
    tests/test_transaction_recovery.py

run_pytest \
    "[7] TRANSACTION FAILURE / ROLLBACK" \
    tests/test_transaction_failure_rollback.py

run_pytest \
    "[8] ATOMICITY" \
    tests/test_atomicity.py

run_pytest \
    "[9] COMMIT MARKER" \
    tests/test_commit_marker.py

run_pytest \
    "[10] CRASH RECOVERY" \
    tests/test_crash_recovery.py

run_pytest \
    "[11] PERSISTENT RESTART RECOVERY" \
    tests/test_persistent_restart_recovery.py

run_pytest \
    "[12] PHYSICAL RESTART DURABILITY" \
    tests/test_physical_restart_durability.py

echo
echo "======================================================================"
echo "[13] STORAGE / INTEGRITY"
echo "======================================================================"

run_pytest \
    "[13] OBJECT INTEGRITY" \
    tests/test_object_integrity.py

run_pytest \
    "[14] PARTIAL WRITE RELIABILITY" \
    tests/test_partial_write_reliability.py

run_pytest \
    "[15] DATABASE FAILURE RELIABILITY" \
    tests/test_database_failure_reliability.py

echo
echo "======================================================================"
echo "[16] QUOTA / ALLOCATION"
echo "======================================================================"

run_pytest \
    "[16] QUOTA" \
    tests/test_quota.py

run_pytest \
    "[17] PHYSICAL QUOTA" \
    tests/test_quota_physical.py

run_pytest \
    "[18] ALLOCATION" \
    tests/test_allocation.py

echo
echo "======================================================================"
echo "[19] SECURITY"
echo "======================================================================"

run_pytest \
    "[19] ACCESS CONTROL" \
    tests/test_access_control.py

run_pytest \
    "[20] NAMESPACE SECURITY" \
    tests/test_namespace_security.py

run_pytest \
    "[21] CRYPTO IDENTITY" \
    tests/test_crypto_identity.py

run_pytest \
    "[22] KEY PROTECTION" \
    tests/test_key_protection.py

run_pytest \
    "[23] SECURITY INTEGRITY" \
    tests/test_security_integrity.py

run_pytest \
    "[24] SECURITY FINAL" \
    tests/test_security_final.py

run_pytest \
    "[25] SECURITY OPERATIONAL" \
    tests/test_security_operational.py

run_pytest \
    "[26] SECURITY PROCESS RESTART" \
    tests/test_security_process_restart.py

echo
echo "======================================================================"
echo "[27] API"
echo "======================================================================"

run_pytest \
    "[27] API TEST SUITE" \
    tests/api/

echo
echo "======================================================================"
echo "[28] TMP / BACKUP TEST CONTAMINATION CHECK"
echo "======================================================================"

TMP_TESTS=$(find tmp -type f \( -name 'test_*.py' -o -name '*_test.py' \) 2>/dev/null | wc -l)

echo "Testes encontrados dentro de tmp/: $TMP_TESTS"

if [ "$TMP_TESTS" -eq 0 ]; then
    echo "[PASS] Nenhum teste histórico dentro de tmp/"
    PASS=$((PASS + 1))
else
    echo "[WARN] Existem $TMP_TESTS arquivos de teste históricos dentro de tmp/"
    WARN=$((WARN + 1))
fi

echo
echo "======================================================================"
echo "[29] GIT"
echo "======================================================================"

git status --short

git fetch origin >/dev/null 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

echo "LOCAL : $LOCAL"
echo "REMOTE: $REMOTE"

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[PASS] Local main sincronizado com origin/main"
    PASS=$((PASS + 1))
else
    echo "[WARN] Local main diferente de origin/main"
    WARN=$((WARN + 1))
fi

echo
echo "======================================================================"
echo "                  FINAL TEST SUMMARY V2"
echo "======================================================================"

echo "PASS : $PASS"
echo "FAIL : $FAIL"
echo "SKIP : $SKIP"
echo "WARN : $WARN"

echo

if [ "$FAIL" -eq 0 ]; then
    echo "======================================================================"
    echo "CLISER DATA NODE — TEST STATUS: PASS"
    echo "======================================================================"
    exit 0
else
    echo "======================================================================"
    echo "CLISER DATA NODE — TEST STATUS: FAIL"
    echo "======================================================================"
    exit 1
fi
