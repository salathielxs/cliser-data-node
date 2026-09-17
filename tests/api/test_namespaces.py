import json
import urllib.error
import urllib.request
import uuid

import pytest

from node.credential_manager import (
    create_api_credential,
    revoke_api_credential_by_id,
)


BASE_URL = "http://127.0.0.1:8000/api/v1"


# ============================================================
# HTTP HELPER
# ============================================================

def request(
    path,
    authorization=None,
    method="GET",
    body=None,
):
    headers = {
        "Accept": "application/json",
    }

    if authorization:
        headers["Authorization"] = authorization

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request_obj = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request_obj,
            timeout=10,
        ) as response:
            raw = response.read().decode("utf-8")

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw

            return response.status, payload

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw

        return exc.code, payload

    except urllib.error.URLError as exc:
        pytest.fail(
            f"API indisponível em {BASE_URL}: {exc}"
        )


# ============================================================
# HELPERS
# ============================================================

def bearer(credential):
    return f"Bearer {credential['token']}"


def unique_namespace(prefix="pytest-ns"):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def create_namespace(
    credential,
    namespace,
    quota_bytes=0,
):
    return request(
        "/namespaces",
        authorization=bearer(credential),
        method="POST",
        body={
            "namespace": namespace,
            "quota_bytes": quota_bytes,
        },
    )


# ============================================================
# FIXTURE — ADMIN
# ============================================================

@pytest.fixture
def admin_credential():
    credential_id = (
        "pytest-namespace-admin-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-namespace-admin",
        role="ADMIN",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


# ============================================================
# FIXTURE — READER
# ============================================================

@pytest.fixture
def reader_credential():
    credential_id = (
        "pytest-namespace-reader-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-namespace-reader",
        role="READER",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


# ============================================================
# 01 — CREATE REQUIRES AUTH
# ============================================================

def test_namespace_create_requires_authentication():
    namespace = unique_namespace()

    status, body = request(
        "/namespaces",
        method="POST",
        body={
            "namespace": namespace,
            "quota_bytes": 0,
        },
    )

    assert status == 401
    assert body["error"]["code"] == "AUTH_REQUIRED"


# ============================================================
# 02 — READER CANNOT CREATE
# ============================================================

def test_reader_cannot_create_namespace(
    reader_credential,
):
    namespace = unique_namespace()

    status, body = create_namespace(
        reader_credential,
        namespace,
    )

    assert status == 403
    assert body["error"]["code"] == "AUTHZ_DENIED"


# ============================================================
# 03 — ADMIN CREATE
# ============================================================

def test_admin_can_create_namespace(
    admin_credential,
):
    namespace = unique_namespace()

    status, body = create_namespace(
        admin_credential,
        namespace,
        1024,
    )

    assert status in (200, 201)

    assert body["namespace"] == namespace
    assert body["quota_bytes"] == 1024
    assert body["status"] in (
        "ACTIVE",
        "ENABLED",
    )


# ============================================================
# 04 — ZERO QUOTA
# ============================================================

def test_namespace_zero_quota(
    admin_credential,
):
    namespace = unique_namespace()

    status, body = create_namespace(
        admin_credential,
        namespace,
        0,
    )

    assert status in (200, 201)

    assert body["namespace"] == namespace
    assert body["quota_bytes"] == 0


# ============================================================
# 05 — DUPLICATE
# ============================================================

def test_duplicate_namespace(
    admin_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        1000,
    )

    assert status in (200, 201)

    status, body = create_namespace(
        admin_credential,
        namespace,
        2000,
    )

    assert status in (400, 409)
    assert "error" in body


# ============================================================
# 06 — EMPTY NAME
# ============================================================

def test_empty_namespace(
    admin_credential,
):
    status, body = create_namespace(
        admin_credential,
        "",
        0,
    )

    assert status == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# 07 — NEGATIVE QUOTA
# ============================================================

def test_negative_quota(
    admin_credential,
):
    namespace = unique_namespace()

    status, body = create_namespace(
        admin_credential,
        namespace,
        -1,
    )

    assert status == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# 08 — NAME > 64
# ============================================================

def test_namespace_too_long(
    admin_credential,
):
    namespace = "x" * 65

    status, body = create_namespace(
        admin_credential,
        namespace,
        0,
    )

    assert status == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# 09 — LIST
# ============================================================

def test_admin_can_list_namespaces(
    admin_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        4096,
    )

    assert status in (200, 201)

    status, body = request(
        "/namespaces",
        authorization=bearer(admin_credential),
    )

    assert status == 200
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)

    names = [
        item["namespace"]
        for item in body["items"]
    ]

    assert namespace in names


# ============================================================
# 10 — LIST REQUIRES AUTH
# ============================================================

def test_namespace_list_requires_authentication():
    status, body = request(
        "/namespaces",
    )

    assert status == 401
    assert body["error"]["code"] == "AUTH_REQUIRED"


# ============================================================
# 11 — GET
# ============================================================

def test_admin_can_get_namespace(
    admin_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        8192,
    )

    assert status in (200, 201)

    status, body = request(
        f"/namespaces/{namespace}",
        authorization=bearer(admin_credential),
    )

    assert status == 200
    assert body["namespace"] == namespace
    assert body["quota_bytes"] == 8192


# ============================================================
# 12 — GET NOT FOUND
# ============================================================

def test_get_nonexistent_namespace(
    admin_credential,
):
    namespace = unique_namespace(
        "pytest-missing"
    )

    status, body = request(
        f"/namespaces/{namespace}",
        authorization=bearer(admin_credential),
    )

    assert status == 404
    assert body["error"]["code"] == "NAMESPACE_NOT_FOUND"


# ============================================================
# 13 — ENABLE
# ============================================================

def test_enable_namespace(
    admin_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        1000,
    )

    assert status in (200, 201)

    status, body = request(
        f"/namespaces/{namespace}/enable",
        authorization=bearer(admin_credential),
        method="POST",
    )

    assert status == 200
    assert body["namespace"] == namespace
    assert body["status"] in (
        "ACTIVE",
        "ENABLED",
    )


# ============================================================
# 14 — DISABLE
# ============================================================

def test_disable_namespace(
    admin_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        1000,
    )

    assert status in (200, 201)

    status, body = request(
        f"/namespaces/{namespace}/disable",
        authorization=bearer(admin_credential),
        method="POST",
    )

    assert status == 200
    assert body["namespace"] == namespace
    assert body["status"] in (
        "DISABLED",
        "INACTIVE",
    )


# ============================================================
# 15 — ENABLE NOT FOUND
# ============================================================

def test_enable_nonexistent_namespace(
    admin_credential,
):
    namespace = unique_namespace(
        "pytest-missing"
    )

    status, body = request(
        f"/namespaces/{namespace}/enable",
        authorization=bearer(admin_credential),
        method="POST",
    )

    assert status == 404
    assert body["error"]["code"] == "NAMESPACE_NOT_FOUND"


# ============================================================
# 16 — DISABLE NOT FOUND
# ============================================================

def test_disable_nonexistent_namespace(
    admin_credential,
):
    namespace = unique_namespace(
        "pytest-missing"
    )

    status, body = request(
        f"/namespaces/{namespace}/disable",
        authorization=bearer(admin_credential),
        method="POST",
    )

    assert status == 404
    assert body["error"]["code"] == "NAMESPACE_NOT_FOUND"


# ============================================================
# 17 — READER GET
# ============================================================

def test_reader_namespace_access(
    admin_credential,
    reader_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        2048,
    )

    assert status in (200, 201)

    status, body = request(
        f"/namespaces/{namespace}",
        authorization=bearer(reader_credential),
    )

    assert status in (200, 403, 404)

    if status == 403:
        assert body["error"]["code"] in (
            "AUTHZ_DENIED",
            "NAMESPACE_ACCESS_DENIED",
        )


# ============================================================
# 18 — READER ENABLE
# ============================================================

def test_reader_cannot_enable_namespace(
    admin_credential,
    reader_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        1000,
    )

    assert status in (200, 201)

    status, body = request(
        f"/namespaces/{namespace}/enable",
        authorization=bearer(reader_credential),
        method="POST",
    )

    assert status == 403
    assert body["error"]["code"] == "AUTHZ_DENIED"


# ============================================================
# 19 — READER DISABLE
# ============================================================

def test_reader_cannot_disable_namespace(
    admin_credential,
    reader_credential,
):
    namespace = unique_namespace()

    status, _ = create_namespace(
        admin_credential,
        namespace,
        1000,
    )

    assert status in (200, 201)

    status, body = request(
        f"/namespaces/{namespace}/disable",
        authorization=bearer(reader_credential),
        method="POST",
    )

    assert status == 403
    assert body["error"]["code"] == "AUTHZ_DENIED"


# ============================================================
# 20 — REVOKED CREDENTIAL
# ============================================================

def test_revoked_credential_rejected():
    credential_id = (
        "pytest-namespace-revoked-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-revoked-namespace",
        role="ADMIN",
    )

    try:
        revoke_api_credential_by_id(
            credential_id
        )

        status, body = request(
            "/namespaces",
            authorization=bearer(credential),
        )

        assert status == 401
        assert body["error"]["code"] == "AUTH_REVOKED"

    finally:
        revoke_api_credential_by_id(
            credential_id
        )


# ============================================================
# 21 — MISSING BODY
# ============================================================

def test_namespace_create_missing_body(
    admin_credential,
):
    status, body = request(
        "/namespaces",
        authorization=bearer(admin_credential),
        method="POST",
    )

    assert status == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# 22 — INVALID QUOTA TYPE
# ============================================================

def test_invalid_quota_type(
    admin_credential,
):
    namespace = unique_namespace()

    status, body = request(
        "/namespaces",
        authorization=bearer(admin_credential),
        method="POST",
        body={
            "namespace": namespace,
            "quota_bytes": "invalid",
        },
    )

    assert status == 422
    assert body["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# SUITE INFO
# ============================================================

print(
    "\n"
    "============================================================\n"
    "14.24.4 — NAMESPACE API TEST SUITE\n"
    "MODE: REAL HTTP / 127.0.0.1:8000\n"
    "============================================================\n"
)
