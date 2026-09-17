import json
import subprocess
import sys
import uuid

BASE = "http://127.0.0.1:8080"
TOKEN = open("config/.idempotency_test_token").read().strip()

results = []

def test(name, args, expected_status, expected_code=None):
    p = subprocess.run(
        ["curl", "-s", "-i", "--max-time", "10", *args],
        capture_output=True,
        text=True,
    )

    raw = p.stdout

    status = None
    for line in raw.splitlines():
        if line.startswith("HTTP/"):
            try:
                status = int(line.split()[1])
            except Exception:
                pass

    body = raw.split("\r\n\r\n", 1)[-1]

    try:
        data = json.loads(body)
    except Exception:
        data = {}

    error = data.get("error", {}) if isinstance(data, dict) else {}
    code = error.get("code")

    ok = status == expected_status

    if expected_code is not None:
        ok = ok and code == expected_code

    results.append((name, ok, status, code))

    print(
        f"[{'PASS' if ok else 'FAIL'}] "
        f"{name:<32} HTTP={status} CODE={code}"
    )

    return raw, data


print()
print("=" * 72)
print("CLISER DATA NODE — FASE 14.22 — FINAL LOGGING AUDIT")
print("=" * 72)
print()

test(
    "HTTP normal",
    [
        "-H", "X-Request-ID: REQ-14-22-FINAL-001",
        f"{BASE}/api/v1/health",
    ],
    200,
)

test(
    "401 AUTH_REQUIRED",
    [
        "-H", "X-Request-ID: REQ-14-22-FINAL-002",
        f"{BASE}/api/v1/namespaces/default/objects/not-found",
    ],
    401,
    "AUTH_REQUIRED",
)

test(
    "404 OBJECT_NOT_FOUND",
    [
        "-H", f"Authorization: Bearer {TOKEN}",
        "-H", "X-Request-ID: REQ-14-22-FINAL-003",
        f"{BASE}/api/v1/namespaces/default/objects/"
        "object-not-found-14-22-final",
    ],
    404,
    "OBJECT_NOT_FOUND",
)

test(
    "422 validation",
    [
        "-H", f"Authorization: Bearer {TOKEN}",
        "-H", "X-Request-ID: REQ-14-22-FINAL-005",
        "-H", "Content-Type: application/json",
        "-X", "POST",
        f"{BASE}/api/v1/namespaces/default/objects",
        "-d", "{}",
    ],
    422,
    "VALIDATION_ERROR",
)

test(
    "414 query too large",
    [
        "-H", "X-Request-ID: REQ-14-22-FINAL-006",
        f"{BASE}/api/v1/health?" + ("x" * 5000),
    ],
    414,
    "QUERY_STRING_TOO_LARGE",
)

test(
    "413 request too large",
    [
        "-H", "X-Request-ID: REQ-14-22-FINAL-007",
        "-H", "Content-Length: 13000000",
        f"{BASE}/api/v1/health",
    ],
    413,
    "REQUEST_BODY_TOO_LARGE",
)

request_id = "REQ-14-22-FINAL-" + uuid.uuid4().hex[:8]

raw, _ = test(
    "Request-ID preservation",
    [
        "-H", f"X-Request-ID: {request_id}",
        f"{BASE}/api/v1/health",
    ],
    200,
)

header_ok = any(
    line.lower() == f"x-request-id: {request_id.lower()}"
    for line in raw.splitlines()
)

if header_ok:
    print("[PASS] Request-ID retornado pelo servidor")
    results.append(("Request-ID header", True, 200, None))
else:
    print("[FAIL] Request-ID não retornado corretamente")
    results.append(("Request-ID header", False, None, None))

print()
print("Validação do módulo de logging...")

try:
    subprocess.run(
        [sys.executable, "-m", "py_compile", "api/logging.py"],
        check=True,
        capture_output=True,
        text=True,
    )

    print("[PASS] api/logging.py compila")
    results.append(("logging.py compilation", True, 200, None))

except subprocess.CalledProcessError:
    print("[FAIL] api/logging.py não compila")
    results.append(("logging.py compilation", False, None, None))

try:
    from api.logging import logger

    assert logger.name == "cliser.api"
    assert logger.handlers

    print("[PASS] Logger cliser.api carregado")
    results.append(("logger structure", True, 200, None))

except Exception as exc:
    print(f"[FAIL] Logger: {type(exc).__name__}")
    results.append(("logger structure", False, None, None))

print()
print("=" * 72)
print("RESULTADO FINAL — FASE 14.22")
print("=" * 72)

passed = sum(1 for _, ok, _, _ in results if ok)
failed = sum(1 for _, ok, _, _ in results if not ok)

print(f"PASS : {passed}")
print(f"FAIL : {failed}")
print(f"TOTAL: {len(results)}")
print()

if failed == 0:
    print("14.22 LOGGING: PASS")
    print("STATUS: FECHADO")
    sys.exit(0)

print("14.22 LOGGING: FAIL")
print("STATUS: NÃO FECHADO")
sys.exit(1)
