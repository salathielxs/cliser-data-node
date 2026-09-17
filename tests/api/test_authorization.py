import json
import urllib.error
import urllib.request
import uuid

import pytest

from node.access_control import AccessDenied, Principal, require_permission
from node.credential_manager import (
    create_api_credential,
    revoke_api_credential_by_id,
)


BASE_URL = "http://127.0.0.1:8000/api/v1"


# ============================================================
# HTTP
# ============================================================

def request(path, authorization=None, method="GET", body=None):
    headers = {
        "Accept": "application/json",
    }

    if authorization:
        headers["Authorization"] = authorization

    data = None

    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        BASE_URL + path,
        method=method,
        headers=headers,
        data=data,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw

            return response.status, parsed

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}

        return exc.code, parsed


def error_code(body):
    return body.get("error", {}).get("code")


# ============================================================
# MATRIZ DE PERMISSÕES
# ============================================================

ROLE_PERMISSIONS = {
    "READER": {
        "object.read",
    },
    "WRITER": {
        "object.create",
        "object.read",
        "object.delete",
    },
    "OWNER": {
        "object.create",
        "object.read",
        "object.delete",
        "namespace.manage",
    },
    "ADMIN": {
        "object.create",
        "object.read",
        "object.delete",
        "namespace.manage",
        "node.manage",
    },
}


# ============================================================
# 14.24.3.1 — PERMISSÕES POSITIVAS
# ============================================================

@pytest.mark.parametrize(
    "role,permission",
    [
        (role, permission)
        for role, permissions in ROLE_PERMISSIONS.items()
        for permission in permissions
    ],
)
def test_role_has_expected_permission(role, permission):
    principal = Principal(
        identity_id=f"test-{role.lower()}",
        role=role,
        namespace=None,
    )

    require_permission(
        principal,
        permission,
    )


# ============================================================
# 14.24.3.2 — PERMISSÕES NEGADAS
# ============================================================

@pytest.mark.parametrize(
    "role,permission",
    [
        ("READER", "node.manage"),
        ("READER", "namespace.manage"),
        ("READER", "object.create"),
        ("READER", "object.delete"),

        ("WRITER", "node.manage"),
        ("WRITER", "namespace.manage"),

        ("OWNER", "node.manage"),
    ],
)
def test_role_denied_for_unauthorized_permission(
    role,
    permission,
):
    principal = Principal(
        identity_id=f"test-{role.lower()}",
        role=role,
        namespace=None,
    )

    with pytest.raises(AccessDenied):
        require_permission(
            principal,
            permission,
        )


# ============================================================
# 14.24.3.3 — ADMIN
# ============================================================

def test_admin_has_node_manage():
    principal = Principal(
        identity_id="test-admin",
        role="ADMIN",
        namespace=None,
    )

    require_permission(
        principal,
        "node.manage",
    )


def test_admin_has_namespace_manage():
    principal = Principal(
        identity_id="test-admin",
        role="ADMIN",
        namespace=None,
    )

    require_permission(
        principal,
        "namespace.manage",
    )


# ============================================================
# 14.24.3.4 — OWNER
# ============================================================

def test_owner_has_namespace_manage():
    principal = Principal(
        identity_id="test-owner",
        role="OWNER",
        namespace=None,
    )

    require_permission(
        principal,
        "namespace.manage",
    )


def test_owner_cannot_manage_node():
    principal = Principal(
        identity_id="test-owner",
        role="OWNER",
        namespace=None,
    )

    with pytest.raises(AccessDenied):
        require_permission(
            principal,
            "node.manage",
        )


# ============================================================
# 14.24.3.5 — WRITER
# ============================================================

def test_writer_can_create():
    principal = Principal(
        identity_id="test-writer",
        role="WRITER",
        namespace=None,
    )

    require_permission(
        principal,
        "object.create",
    )


def test_writer_can_read():
    principal = Principal(
        identity_id="test-writer",
        role="WRITER",
        namespace=None,
    )

    require_permission(
        principal,
        "object.read",
    )


def test_writer_can_delete():
    principal = Principal(
        identity_id="test-writer",
        role="WRITER",
        namespace=None,
    )

    require_permission(
        principal,
        "object.delete",
    )


def test_writer_cannot_manage_namespace():
    principal = Principal(
        identity_id="test-writer",
        role="WRITER",
        namespace=None,
    )

    with pytest.raises(AccessDenied):
        require_permission(
            principal,
            "namespace.manage",
        )


# ============================================================
# 14.24.3.6 — READER
# ============================================================

def test_reader_can_read():
    principal = Principal(
        identity_id="test-reader",
        role="READER",
        namespace=None,
    )

    require_permission(
        principal,
        "object.read",
    )


def test_reader_cannot_create():
    principal = Principal(
        identity_id="test-reader",
        role="READER",
        namespace=None,
    )

    with pytest.raises(AccessDenied):
        require_permission(
            principal,
            "object.create",
        )


def test_reader_cannot_delete():
    principal = Principal(
        identity_id="test-reader",
        role="READER",
        namespace=None,
    )

    with pytest.raises(AccessDenied):
        require_permission(
            principal,
            "object.delete",
        )


# ============================================================
# 14.24.3.7 — HTTP INTEGRATION
# ============================================================

@pytest.fixture
def reader_credential():
    credential_id = (
        "pytest-authz-reader-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-reader",
        role="READER",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


def test_reader_is_authenticated(reader_credential):
    status, body = request(
        "/auth/me",
        authorization=f"Bearer {reader_credential['token']}",
    )

    assert status == 200
    assert body["authenticated"] is True
    assert body["identity_id"] == "pytest-reader"
    assert body["role"] == "READER"
    assert body["credential_id"] == reader_credential["credential_id"]


def test_reader_cannot_access_metrics(reader_credential):
    status, body = request(
        "/metrics",
        authorization=f"Bearer {reader_credential['token']}",
    )

    assert status == 403
    assert error_code(body) == "AUTHZ_DENIED"

    details = body["error"]["details"]

    assert details["permission"] == "node.manage"
    assert details["identity_id"] == "pytest-reader"
    assert details["role"] == "READER"


def test_revoked_credential_is_rejected(reader_credential):
    credential_id = reader_credential["credential_id"]
    token = reader_credential["token"]

    assert revoke_api_credential_by_id(
        credential_id
    ) is True

    status, body = request(
        "/auth/me",
        authorization=f"Bearer {token}",
    )

    assert status == 401
    assert error_code(body) == "AUTH_REVOKED"
