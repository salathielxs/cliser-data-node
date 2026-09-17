#!/data/data/com.termux/files/usr/bin/bash

set -u

ROOT="$HOME/cliser-data-node"
cd "$ROOT" || exit 1

PASS=0
FAIL=0
WARN=0

run_check() {
    local NAME="$1"
    shift

    echo
    echo "======================================================================"
    echo "$NAME"
    echo "======================================================================"

    if "$@"; then
        echo "[PASS] $NAME"
        PASS=$((PASS + 1))
    else
        echo "[FAIL] $NAME"
        FAIL=$((FAIL + 1))
    fi
}

echo "======================================================================"
echo "          CLISER DATA NODE — FULL AUTOMATED TEST"
echo "======================================================================"
echo "ROOT: $ROOT"
echo "DATE: $(date)"
echo

# ----------------------------------------------------------------------
# 1. GIT
# ----------------------------------------------------------------------

echo "======================================================================"
echo "[1] GIT STATE"
echo "======================================================================"

git branch --show-current
git log -3 --oneline --decorate
git status --short

echo

# ----------------------------------------------------------------------
# 2. PYTHON
# ----------------------------------------------------------------------

echo "======================================================================"
echo "[2] PYTHON ENVIRONMENT"
echo "======================================================================"

python --version
python -c 'import sys; print("Python executable:", sys.executable)'
python -c 'import platform; print("Platform:", platform.platform())'

# ----------------------------------------------------------------------
# 3. PYTHON SYNTAX
# ----------------------------------------------------------------------

run_check \
    "[3] PYTHON COMPILE CHECK" \
    python -m compileall -q api node cli scripts tests

# ----------------------------------------------------------------------
# 4. PYTEST AVAILABILITY
# ----------------------------------------------------------------------

echo
echo "======================================================================"
echo "[4] PYTEST"
echo "======================================================================"

if python -m pytest --version >/dev/null 2>&1; then
    python -m pytest --version
    echo "[PASS] pytest disponível"
    PASS=$((PASS + 1))
else
    echo "[FAIL] pytest não está disponível"
    FAIL=$((FAIL + 1))
fi

# ----------------------------------------------------------------------
# 5. UNIT / FULL TEST SUITE
# ----------------------------------------------------------------------

if python -m pytest --version >/dev/null 2>&1; then

    run_check \
        "[5] FULL TEST SUITE" \
        python -m pytest -q

    # ------------------------------------------------------------------
    # 6. TRANSACTION / RECOVERY
    # ------------------------------------------------------------------

    run_check \
        "[6] TRANSACTION RECOVERY" \
        python -m pytest -q tests/test_transaction_recovery.py

    run_check \
        "[7] TRANSACTION FAILURE / ROLLBACK" \
        python -m pytest -q tests/test_transaction_failure_rollback.py

    run_check \
        "[8] ATOMICITY" \
        python -m pytest -q tests/test_atomicity.py

    run_check \
        "[9] COMMIT MARKER" \
        python -m pytest -q tests/test_commit_marker.py

    # ------------------------------------------------------------------
    # 10. RECOVERY
    # ------------------------------------------------------------------

    run_check \
        "[10] CRASH RECOVERY" \
        python -m pytest -q tests/test_crash_recovery.py

    run_check \
        "[11] PERSISTENT RESTART RECOVERY" \
        python -m pytest -q tests/test_persistent_restart_recovery.py

    run_check \
        "[12] PHYSICAL RESTART DURABILITY" \
        python -m pytest -q tests/test_physical_restart_durability.py

    # ------------------------------------------------------------------
    # 13. STORAGE / INTEGRITY
    # ------------------------------------------------------------------

    run_check \
        "[13] OBJECT INTEGRITY" \
        python -m pytest -q tests/test_object_integrity.py

    run_check \
        "[14] PARTIAL WRITE RELIABILITY" \
        python -m pytest -q tests/test_partial_write_reliability.py

    run_check \
        "[15] DATABASE FAILURE RELIABILITY" \
        python -m pytest -q tests/test_database_failure_reliability.py

    # ------------------------------------------------------------------
    # 16. QUOTA / ALLOCATION
    # ------------------------------------------------------------------

    run_check \
        "[16] QUOTA" \
        python -m pytest -q tests/test_quota.py

    run_check \
        "[17] PHYSICAL QUOTA" \
        python -m pytest -q tests/test_quota_physical.py

    run_check \
        "[18] ALLOCATION" \
        python -m pytest -q tests/test_allocation.py

    # ------------------------------------------------------------------
    # 19. SECURITY
    # ------------------------------------------------------------------

    run_check \
        "[19] ACCESS CONTROL" \
        python -m pytest -q tests/test_access_control.py

    run_check \
        "[20] NAMESPACE SECURITY" \
        python -m pytest -q tests/test_namespace_security.py

    run_check \
        "[21] CRYPTO IDENTITY" \
        python -m pytest -q tests/test_crypto_identity.py

    run_check \
        "[22] KEY PROTECTION" \
        python -m pytest -q tests/test_key_protection.py

    run_check \
        "[23] SECURITY INTEGRITY" \
        python -m pytest -q tests/test_security_integrity.py

    run_check \
        "[24] SECURITY FINAL" \
        python -m pytest -q tests/test_security_final.py

    run_check \
        "[25] SECURITY OPERATIONAL" \
        python -m pytest -q tests/test_security_operational.py

    run_check \
        "[26] SECURITY PROCESS RESTART" \
        python -m pytest -q tests/test_security_process_restart.py

    # ------------------------------------------------------------------
    # 27. API
    # ------------------------------------------------------------------

    run_check \
        "[27] API TEST SUITE" \
        python -m pytest -q tests/api/

fi

# ----------------------------------------------------------------------
# 28. GIT INTEGRITY
# ----------------------------------------------------------------------

echo
echo "======================================================================"
echo "[28] GIT REPOSITORY"
echo "======================================================================"

git status

echo

git fetch origin >/dev/null 2>&1

if git diff --quiet origin/main..HEAD &&
   git diff --quiet HEAD..origin/main; then
    echo "[PASS] Local main e origin/main estão sincronizados"
    PASS=$((PASS + 1))
else
    echo "[WARN] Local main e origin/main possuem diferenças"
    WARN=$((WARN + 1))
fi

# ----------------------------------------------------------------------
# FINAL
# ----------------------------------------------------------------------

echo
echo "======================================================================"
echo "                  FINAL TEST SUMMARY"
echo "======================================================================"

echo "PASS : $PASS"
echo "FAIL : $FAIL"
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
