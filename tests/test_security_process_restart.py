from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(code: str, input_data: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, "-c", code],
        cwd=ROOT,
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(ROOT),
        },
        input=input_data,
        text=True,
        capture_output=True,
    )


def ok(label: str):
    print(f"{label}: OK")


def fail(label: str, detail: str = ""):
    print(f"{label}: FAIL")
    if detail:
        print(detail)
    raise SystemExit(1)


def main():
    print("CLISER DATA NODE — PROCESS RESTART SECURITY TEST")
    print("=" * 50)

    # --------------------------------------------------
    # PROCESSO A
    # --------------------------------------------------
    process_a = r'''
from node import crypto_identity

password = input()

crypto_identity.unlock(password)

if not crypto_identity.is_unlocked():
    raise SystemExit("UNLOCK FAILED")

payload = b"CLISER-PROCESS-RESTART-TEST"
signature = crypto_identity.sign(payload)

if not crypto_identity.verify(payload, signature):
    raise SystemExit("SIGNATURE FAILED")

print("PROCESS_A_SIGNATURE_OK")
'''

    password = input("Senha da identidade: ")

    if not password:
        fail("PASSWORD", "Senha vazia.")

    result_a = run(
        process_a,
        input_data=password + "\n",
    )

    if result_a.returncode != 0:
        fail(
            "PROCESS A",
            result_a.stderr.strip(),
        )

    if "PROCESS_A_SIGNATURE_OK" not in result_a.stdout:
        fail(
            "PROCESS A",
            result_a.stdout,
        )

    ok("PROCESS A UNLOCK + SIGN")

    # --------------------------------------------------
    # PROCESSO B
    # --------------------------------------------------
    process_b = r'''
from node import crypto_identity

if crypto_identity.is_unlocked():
    raise SystemExit("PRIVATE KEY INHERITED")

try:
    crypto_identity.sign(
        b"CLISER-PROCESS-RESTART-TEST"
    )
except Exception:
    print("PROCESS_B_BLOCKED_OK")
else:
    raise SystemExit("BLOCKED SIGNING ACCEPTED")
'''

    result_b = run(process_b)

    if result_b.returncode != 0:
        fail(
            "PROCESS B INITIAL LOCK",
            result_b.stderr.strip(),
        )

    if "PROCESS_B_BLOCKED_OK" not in result_b.stdout:
        fail(
            "PROCESS B INITIAL LOCK",
            result_b.stdout,
        )

    ok("PROCESS B STARTS LOCKED")

    # --------------------------------------------------
    # PROCESSO C
    # --------------------------------------------------
    process_c = r'''
from node import crypto_identity

password = input()

if crypto_identity.is_unlocked():
    raise SystemExit("KEY ALREADY UNLOCKED")

crypto_identity.unlock(password)

payload = b"CLISER-PROCESS-RESTART-TEST"

signature = crypto_identity.sign(payload)

if not crypto_identity.verify(payload, signature):
    raise SystemExit("RE-SIGNATURE FAILED")

crypto_identity.lock()

if crypto_identity.is_unlocked():
    raise SystemExit("LOCK FAILED")

print("PROCESS_C_REUNLOCK_OK")
'''

    result_c = run(
        process_c,
        input_data=password + "\n",
    )

    if result_c.returncode != 0:
        fail(
            "PROCESS C REUNLOCK",
            result_c.stderr.strip(),
        )

    if "PROCESS_C_REUNLOCK_OK" not in result_c.stdout:
        fail(
            "PROCESS C REUNLOCK",
            result_c.stdout,
        )

    ok("PROCESS C REUNLOCK + SIGN + LOCK")

    # --------------------------------------------------
    # FINAL
    # --------------------------------------------------
    print()
    print("=" * 50)
    print("PROCESS RESTART SECURITY: PASS")
    print("FASE 13.7.3 — ISOLAMENTO ENTRE PROCESSOS VALIDADO")
    print("=" * 50)


if __name__ == "__main__":
    main()
