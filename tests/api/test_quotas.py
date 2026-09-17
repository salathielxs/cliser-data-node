from __future__ import annotations

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
# HTTP HELPERS
# ============================================================

def http_request(
    method: str,
    path: str,
    token: str | None = None,
    body: bytes | None = None,
):
    headers = {
        "Accept": "application/json",
    }

    if body is not None:
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        BASE_URL + path,
        method=method,
        headers=headers,
        data=body,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10,
        ) as response:
            return (
                response.status,
                dict(response.headers),
                response.read(),
            )

    except urllib.error.HTTPError as exc:
        return (
            exc.code,
            dict(exc.headers),
            exc.read(),
        )


def json_body(body: bytes) -> dict:
    return json.loads(body.decode("utf-8"))


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def json_request(
    method: str,
    path: str,
    token: str | None,
    payload: dict,
):
    return http_request(
        method,
        path,
        token,
        json.dumps(payload).encode("utf-8"),
    )


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def admin_credential():
    credential_id = unique_name(
        "pytest-quota-admin"
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name(
            "pytest-quota-admin-identity"
        ),
        role="ADMIN",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


@pytest.fixture
def reader_credential():
    credential_id = unique_name(
        "pytest-quota-reader"
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name(
            "pytest-quota-reader-identity"
        ),
        role="READER",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


@pytest.fixture
def writer_credential():
    credential_id = unique_name(
        "pytest-quota-writer"
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name(
            "pytest-quota-writer-identity"
        ),
        role="WRITER",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


@pytest.fixture
def namespace_with_admin(
    admin_credential,
):
    namespace = unique_name(
        "pytest-quota-ns"
    )

    status, _, body = json_request(
        "POST",
        "/namespaces",
        admin_credential["token"],
        {
            "namespace": namespace,
        },
    )

    assert status in {200, 201}

    return namespace


# ============================================================
# 01 — GET SUCCESS
# ============================================================

def test_quota_get_success(
    admin_credential,
    namespace_with_admin,
):
    status, headers, body = http_request(
        "GET",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["namespace"] == namespace_with_admin
    assert isinstance(data["quota_bytes"], int)
    assert isinstance(data["used_bytes"], int)
    assert (
        data["available_bytes"] is None
        or isinstance(data["available_bytes"], int)
    )


# ============================================================
# 02 — GET REQUIRES AUTHENTICATION
# ============================================================

def test_quota_get_requires_authentication(
    namespace_with_admin,
):
    status, _, body = http_request(
        "GET",
        f"/namespaces/{namespace_with_admin}/quota",
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] == "AUTH_REQUIRED"


# ============================================================
# 03 — PUT SUCCESS
# ============================================================

def test_quota_update_success(
    admin_credential,
    namespace_with_admin,
):
    quota_bytes = 1024 * 1024

    status, headers, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": quota_bytes,
            "mode": "LOGICAL",
        },
    )

    assert status == 200
    assert headers.get(
        "content-type",
        "",
    ).startswith("application/json")

    data = json_body(body)

    assert data["namespace"] == namespace_with_admin
    assert data["quota_bytes"] == quota_bytes
    assert data["used_bytes"] == 0
    assert data["available_bytes"] == quota_bytes


# ============================================================
# 04 — PUT REQUIRES AUTHENTICATION
# ============================================================

def test_quota_update_requires_authentication(
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        None,
        {
            "quota_bytes": 1024,
        },
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] == "AUTH_REQUIRED"


# ============================================================
# 05 — READER CANNOT MANAGE QUOTA
# ============================================================

def test_quota_update_requires_quota_manage(
    reader_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        reader_credential["token"],
        {
            "quota_bytes": 1024,
        },
    )

    assert status == 403

    data = json_body(body)

    assert data["error"]["code"] in {
        "AUTHZ_DENIED",
        "PERMISSION_DENIED",
        "AUTH_FORBIDDEN",
    }


# ============================================================
# 06 — READER CAN READ QUOTA
# ============================================================

def test_quota_get_requires_namespace_read(
    admin_credential,
    reader_credential,
    namespace_with_admin,
):
    status, _, _ = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 2048,
        },
    )

    assert status == 200

    status, _, body = http_request(
        "GET",
        f"/namespaces/{namespace_with_admin}/quota",
        reader_credential["token"],
    )

    assert status == 403

    data = json_body(body)

    assert data["error"]["code"] in {
        "AUTHZ_DENIED",
        "PERMISSION_DENIED",
        "AUTH_FORBIDDEN",
    }


# ============================================================
# 07 — ZERO = UNLIMITED
# ============================================================

def test_quota_zero_is_unlimited(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 0,
            "mode": "LOGICAL",
        },
    )

    assert status == 200

    data = json_body(body)

    assert data["quota_bytes"] == 0
    assert data["used_bytes"] == 0
    assert data["available_bytes"] is None


# ============================================================
# 08 — NEGATIVE QUOTA
# ============================================================

def test_quota_negative_rejected(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": -1,
        },
    )

    assert status == 422

    data = json_body(body)

    assert data["error"]["code"] == "VALIDATION_ERROR"


# ============================================================
# 09 — INVALID MODE
# ============================================================

def test_quota_invalid_mode(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 1024,
            "mode": "INVALID",
        },
    )

    assert status == 400

    data = json_body(body)

    assert data["error"]["code"] == "QUOTA_UPDATE_ERROR"
    assert "Modo de quota inválido" in data["error"]["message"]


# ============================================================
# 10 — LOGICAL MODE
# ============================================================

def test_quota_logical_mode(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 4096,
            "mode": "LOGICAL",
        },
    )

    assert status == 200

    data = json_body(body)

    assert data["quota_bytes"] == 4096
    assert data["used_bytes"] == 0
    assert data["available_bytes"] == 4096


# ============================================================
# 11 — PHYSICAL MODE
# ============================================================

def test_quota_physical_mode(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 4096,
            "mode": "PHYSICAL",
        },
    )

    assert status == 200

    data = json_body(body)

    assert data["quota_bytes"] == 4096
    assert data["used_bytes"] >= 0
    assert data["available_bytes"] >= 0


# ============================================================
# 12 — HYBRID MODE
# ============================================================

def test_quota_hybrid_mode(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 4096,
            "mode": "HYBRID",
        },
    )

    assert status == 200

    data = json_body(body)

    assert data["quota_bytes"] == 4096
    assert data["used_bytes"] >= 0
    assert data["available_bytes"] >= 0


# ============================================================
# 13 — NAMESPACE NOT FOUND
# ============================================================

def test_quota_namespace_not_found(
    admin_credential,
):
    namespace = unique_name(
        "pytest-nonexistent-quota-ns"
    )

    status, _, body = http_request(
        "GET",
        f"/namespaces/{namespace}/quota",
        admin_credential["token"],
    )

    assert status in {403, 404}

    data = json_body(body)

    assert data["error"]["code"] in {
        "NAMESPACE_NOT_FOUND",
        "NAMESPACE_ACCESS_DENIED",
        "QUOTA_NOT_FOUND",
    }


# ============================================================
# 14 — QUOTA UPDATE IS PERSISTENT
# ============================================================

def test_quota_update_persists(
    admin_credential,
    namespace_with_admin,
):
    first_value = 8192
    second_value = 16384

    status, _, _ = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": first_value,
        },
    )

    assert status == 200

    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": second_value,
        },
    )

    assert status == 200

    data = json_body(body)

    assert data["quota_bytes"] == second_value

    status, _, body = http_request(
        "GET",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["quota_bytes"] == second_value


# ============================================================
# 15 — RESPONSE CONTRACT
# ============================================================

def test_quota_response_contract(
    admin_credential,
    namespace_with_admin,
):
    status, _, body = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": 32768,
            "mode": "LOGICAL",
        },
    )

    assert status == 200

    data = json_body(body)

    required = {
        "namespace",
        "quota_bytes",
        "used_bytes",
        "available_bytes",
    }

    assert required.issubset(data.keys())

    assert isinstance(
        data["namespace"],
        str,
    )

    assert isinstance(
        data["quota_bytes"],
        int,
    )

    assert isinstance(
        data["used_bytes"],
        int,
    )

    assert (
        data["available_bytes"] is None
        or isinstance(
            data["available_bytes"],
            int,
        )
    )


# ============================================================
# 16 — OPENAPI CONTRACT
# ============================================================

def test_quota_openapi_contract():
    status, _, body = http_request(
        "GET",
        "/openapi.json",
    )

    assert status == 200

    data = json_body(body)
    paths = data["paths"]

    path = "/api/v1/namespaces/{namespace}/quota"

    assert path in paths

    operations = paths[path]

    assert "get" in operations
    assert "put" in operations

    get_operation = operations["get"]
    put_operation = operations["put"]

    assert (
        get_operation["operationId"]
        == "get_quota_api_v1_namespaces__namespace__quota_get"
    )

    assert (
        put_operation["operationId"]
        == "update_quota_api_v1_namespaces__namespace__quota_put"
    )

    assert "200" in get_operation["responses"]
    assert "200" in put_operation["responses"]

    assert "QuotaResponse" in json.dumps(
        get_operation
    )

    assert "QuotaResponse" in json.dumps(
        put_operation
    )


# ============================================================
# 17 — GET AFTER UPDATE
# ============================================================

def test_quota_get_after_update(
    admin_credential,
    namespace_with_admin,
):
    quota_bytes = 65536

    status, _, _ = json_request(
        "PUT",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
        {
            "quota_bytes": quota_bytes,
        },
    )

    assert status == 200

    status, _, body = http_request(
        "GET",
        f"/namespaces/{namespace_with_admin}/quota",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["namespace"] == namespace_with_admin
    assert data["quota_bytes"] == quota_bytes
    assert data["used_bytes"] == 0
    assert data["available_bytes"] == quota_bytes
