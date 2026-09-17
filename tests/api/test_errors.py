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
# HTTP
# ============================================================

def request(
    path: str,
    authorization: str | None = None,
    method: str = "GET",
    body=None,
    headers: dict | None = None,
):
    request_headers = {
        "Accept": "application/json",
    }

    if authorization:
        request_headers["Authorization"] = (
            f"Bearer {authorization}"
        )

    if headers:
        request_headers.update(headers)

    data = None

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        BASE_URL + path,
        headers=request_headers,
        method=method,
        data=data,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw

            return (
                response.status,
                dict(response.headers),
                payload,
            )

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw

        return (
            exc.code,
            dict(exc.headers),
            payload,
        )

    except urllib.error.URLError as exc:
        pytest.fail(
            f"API indisponível em {BASE_URL}: {exc}"
        )


# ============================================================
# HELPERS
# ============================================================

def header_value(headers, name: str):
    target = name.lower()

    for key, value in headers.items():
        if key.lower() == target:
            return value

    return None


def error_code(body):
    return body.get("error", {}).get("code")


def assert_error_contract(
    status,
    headers,
    body,
    expected_status,
    expected_code,
):
    assert status == expected_status
    assert isinstance(body, dict)

    assert "error" in body
    assert isinstance(body["error"], dict)

    error = body["error"]

    assert error["code"] == expected_code
    assert isinstance(error["message"], str)
    assert error["message"]

    assert "request_id" in error
    assert error["request_id"]

    request_id_header = header_value(
        headers,
        "X-Request-ID",
    )

    assert request_id_header
    assert request_id_header == error["request_id"]


def unique_namespace(prefix="pytest-errors"):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def admin_credential():
    credential_id = (
        "pytest-errors-admin-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-errors-admin",
        role="ADMIN",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


@pytest.fixture
def reader_credential():
    credential_id = (
        "pytest-errors-reader-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-errors-reader",
        role="READER",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


# ============================================================
# 01 — 401 AUTH_REQUIRED
# ============================================================

def test_error_auth_required():
    status, headers, body = request(
        "/namespaces",
    )

    assert_error_contract(
        status,
        headers,
        body,
        401,
        "AUTH_REQUIRED",
    )


# ============================================================
# 02 — 401 AUTH_INVALID
# ============================================================

def test_error_auth_invalid():
    status, headers, body = request(
        "/namespaces",
        authorization="invalid-token",
    )

    assert_error_contract(
        status,
        headers,
        body,
        401,
        "AUTH_INVALID",
    )


# ============================================================
# 03 — 403 AUTHZ_DENIED
# ============================================================

def test_error_authorization_denied(
    reader_credential,
):
    status, headers, body = request(
        "/namespaces",
        authorization=reader_credential["token"],
        method="POST",
        body={
            "namespace": unique_namespace(),
            "quota_bytes": 0,
        },
    )

    assert_error_contract(
        status,
        headers,
        body,
        403,
        "AUTHZ_DENIED",
    )


# ============================================================
# 04 — 404 NAMESPACE_NOT_FOUND
# ============================================================

def test_error_namespace_not_found(
    admin_credential,
):
    namespace = unique_namespace(
        "pytest-errors-missing"
    )

    status, headers, body = request(
        f"/namespaces/{namespace}",
        authorization=admin_credential["token"],
    )

    assert_error_contract(
        status,
        headers,
        body,
        404,
        "NAMESPACE_NOT_FOUND",
    )


# ============================================================
# 05 — 422 VALIDATION_ERROR
# ============================================================

def test_error_validation_error(
    admin_credential,
):
    status, headers, body = request(
        "/namespaces",
        authorization=admin_credential["token"],
        method="POST",
        body={},
    )

    assert_error_contract(
        status,
        headers,
        body,
        422,
        "VALIDATION_ERROR",
    )

    details = body["error"].get("details")

    assert isinstance(details, dict)
    assert "errors" in details
    assert isinstance(details["errors"], list)
    assert details["errors"]


# ============================================================
# 06 — REQUEST ID CONSISTENCY
# ============================================================

def test_error_request_id_consistency():
    status, headers, body = request(
        "/namespaces",
    )

    assert status == 401

    request_id_body = (
        body["error"]["request_id"]
    )

    request_id_header = header_value(
        headers,
        "X-Request-ID",
    )

    assert request_id_body
    assert request_id_header
    assert request_id_body == request_id_header


# ============================================================
# 07 — NO RAW INTERNAL EXCEPTION
# ============================================================

def test_error_response_has_no_raw_exception():
    status, headers, body = request(
        "/namespaces",
    )

    assert status == 401

    text = json.dumps(
        body,
        ensure_ascii=False,
    ).lower()

    assert "traceback" not in text
    assert "stack trace" not in text
    assert "exception" not in text


# ============================================================
# 08 — ERROR ENVELOPE IS OBJECT
# ============================================================

def test_error_envelope_structure():
    status, headers, body = request(
        "/namespaces",
    )

    assert status == 401

    error = body["error"]

    assert isinstance(error, dict)

    required = {
        "code",
        "message",
        "request_id",
    }

    assert required.issubset(error.keys())


# ============================================================
# 09 — REQUEST ID IS UNIQUE BETWEEN REQUESTS
# ============================================================

def test_error_request_ids_are_generated_per_request():
    result_a = request("/namespaces")
    result_b = request("/namespaces")

    status_a, headers_a, body_a = result_a
    status_b, headers_b, body_b = result_b

    assert status_a == 401
    assert status_b == 401

    request_id_a = body_a["error"]["request_id"]
    request_id_b = body_b["error"]["request_id"]

    assert request_id_a
    assert request_id_b
    assert request_id_a != request_id_b
