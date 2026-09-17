from pathlib import Path
import os
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "registry.db"

print("=" * 68)
print("CLISER DATA NODE — 15.2.7-G.10 FINAL SECURITY CLASSIFICATION")
print("=" * 68)

checks = []


def add(name, status, detail=""):
    checks.append((name, status, detail))
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def run_python_script(script):
    proc = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True,
        capture_output=True,
    )
    return proc


# ================================================================
# 1. SQLite
# ================================================================

try:
    conn = sqlite3.connect(DB)
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]

    add(
        "SQLite integrity",
        "PASS" if result == "ok" else "FAIL",
        result,
    )

except Exception as exc:
    add("SQLite integrity", "FAIL", repr(exc))

finally:
    try:
        conn.close()
    except Exception:
        pass


# ================================================================
# 2. Security integrity script
# ================================================================

proc = run_python_script("tests/test_security_integrity.py")

if proc.returncode == 0:
    add("Security integrity validation", "PASS")
else:
    add("Security integrity validation", "FAIL")
    print(proc.stdout)
    print(proc.stderr)


# ================================================================
# 3. Namespace isolation script
# ================================================================

proc = run_python_script("tests/test_namespace_isolation.py")

if proc.returncode == 0:
    add("Namespace isolation validation", "PASS")
else:
    add("Namespace isolation validation", "FAIL")
    print(proc.stdout)
    print(proc.stderr)


# ================================================================
# 4. API suite
# ================================================================

proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/api",
    ],
    cwd=ROOT,
    env={**os.environ, "PYTHONPATH": str(ROOT)},
    text=True,
    capture_output=True,
)

if proc.returncode == 0:
    add("API security suite", "PASS")
else:
    add("API security suite", "FAIL")
    print(proc.stdout)
    print(proc.stderr)


# ================================================================
# 5. Full regression suite
# ================================================================

proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        "-q",
    ],
    cwd=ROOT,
    env={**os.environ, "PYTHONPATH": str(ROOT)},
    text=True,
    capture_output=True,
)

if proc.returncode == 0:
    add("Full regression suite", "PASS")
else:
    add("Full regression suite", "FAIL")
    print(proc.stdout)
    print(proc.stderr)


# ================================================================
# 6. Compile
# ================================================================

proc = subprocess.run(
    [
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "api",
        "node",
    ],
    cwd=ROOT,
    env={**os.environ, "PYTHONPATH": str(ROOT)},
    text=True,
    capture_output=True,
)

add(
    "Python compile check",
    "PASS" if proc.returncode == 0 else "FAIL",
)


# ================================================================
# FINAL
# ================================================================

print()
print("-" * 68)

failures = [
    item for item in checks
    if item[1] == "FAIL"
]

print("CHECKS:", len(checks))
print("FAILURES:", len(failures))

print()

if failures:
    print("FINAL CLASSIFICATION: REVIEW")

    for name, status, detail in failures:
        print(f" - {name}: {detail}")

else:
    print("FINAL CLASSIFICATION: PASS")

print("=" * 68)
