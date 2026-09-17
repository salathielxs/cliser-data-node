from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

from node.credential_manager import (
    create_api_credential,
    revoke_api_credential_by_id,
)
from node.registry import connect


BASE_URL = os.getenv(
    "CLISER_TEST_BASE_URL",
    "http://127.0.0.1:8000",
)


def http_request(
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
):
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None

    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        BASE_URL + path,
        method=method,
        headers=headers,
        data=data,
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
    return json.loads(body.decode())


def unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
def admin_credential():
    credential_id = unique_name("pytest-148-admin")

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name("pytest-148-admin-identity"),
        role="ADMIN",
    )

    yield credential

    revoke_api_credential_by_id(credential_id)


@pytest.fixture(scope="module")
def namespace(admin_credential):
    namespace = unique_name("pytest-148-ns")

    code, _, body = http_request(
        "POST",
        "/api/v1/namespaces",
        admin_credential["token"],
        {
            "namespace": namespace,
        },
    )

    if code not in (200, 201):
        pytest.fail(
            "Falha ao criar namespace: "
            f"{code} {body.decode(errors='replace')}"
        )

    return namespace


@pytest.fixture(scope="module")
def object_fixture(admin_credential, namespace):
    payload = {
        "data": base64.b64encode(
            b"CLISER DATA NODE 14.24.8 METADATA MANIFEST"
        ).decode()
    }

    code, _, body = http_request(
        "POST",
        f"/api/v1/namespaces/{namespace}/objects",
        admin_credential["token"],
        payload,
    )

    if code not in (200, 201):
        pytest.fail(
            "Falha ao criar objeto de teste: "
            f"{code} {body.decode(errors='replace')}"
        )

    data = json_body(body)

    return {
        "object_id": data["object_id"],
        "namespace": namespace,
        "response": data,
    }


def test_metadata_success(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/metadata",
        admin_credential["token"],
    )

    assert code == 200, body.decode(errors="replace")

    data = json_body(body)

    assert data["object_id"] == object_id
    assert data["namespace"] == namespace
    assert data["status"] == "ACTIVE"
    assert isinstance(data["size"], int)
    assert data["size"] > 0
    assert isinstance(data["content_hash"], str)
    assert data["content_hash"]


def test_metadata_without_auth(
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/metadata",
    )

    assert code == 401

    data = json_body(body)

    assert data["error"]["code"] == "AUTH_REQUIRED"


def test_metadata_not_found(
    admin_credential,
    namespace,
):
    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        "OBJECT-NOT-FOUND-14-24-8/metadata",
        admin_credential["token"],
    )

    assert code == 404

    data = json_body(body)

    assert data["error"]["code"] == "OBJECT_NOT_FOUND"


def test_metadata_namespace_mismatch(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]

    wrong_namespace = unique_name(
        "pytest-148-wrong-ns"
    )

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{wrong_namespace}/objects/"
        f"{object_id}/metadata",
        admin_credential["token"],
    )

    assert code in (403, 404)

    data = json_body(body)

    assert data["error"]["code"] in {
        "NAMESPACE_NOT_FOUND",
        "NAMESPACE_ACCESS_DENIED",
        "OBJECT_NAMESPACE_ERROR",
        "OBJECT_NOT_FOUND",
    }


def test_manifest_success(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/manifest",
        admin_credential["token"],
    )

    assert code == 200, body.decode(errors="replace")

    data = json_body(body)

    assert data["object_id"] == object_id
    assert data["namespace"] == namespace
    assert data["status"] == "ACTIVE"

    assert isinstance(data["total_size"], int)
    assert data["total_size"] > 0

    assert isinstance(data["block_size"], int)
    assert data["block_size"] > 0

    assert isinstance(data["block_count"], int)
    assert data["block_count"] >= 1

    assert isinstance(data["blocks"], list)

    assert data["block_count"] == len(
        data["blocks"]
    )


def test_manifest_without_auth(
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/manifest",
    )

    assert code == 401

    data = json_body(body)

    assert data["error"]["code"] == "AUTH_REQUIRED"


def test_manifest_not_found(
    admin_credential,
    namespace,
):
    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        "MANIFEST-NOT-FOUND-14-24-8/manifest",
        admin_credential["token"],
    )

    assert code == 404

    data = json_body(body)

    assert data["error"]["code"] == "MANIFEST_NOT_FOUND"


def test_manifest_namespace_mismatch(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]

    wrong_namespace = unique_name(
        "pytest-148-manifest-wrong"
    )

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{wrong_namespace}/objects/"
        f"{object_id}/manifest",
        admin_credential["token"],
    )

    assert code in (403, 404)

    data = json_body(body)

    assert data["error"]["code"] in {
        "NAMESPACE_NOT_FOUND",
        "NAMESPACE_ACCESS_DENIED",
        "MANIFEST_NAMESPACE_ERROR",
        "MANIFEST_NOT_FOUND",
    }


def test_manifest_block_structure(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/manifest",
        admin_credential["token"],
    )

    assert code == 200

    data = json_body(body)

    for block in data["blocks"]:
        assert set(block.keys()) == {
            "index",
            "block_id",
            "size",
        }

        assert isinstance(block["index"], int)
        assert isinstance(block["block_id"], str)
        assert block["block_id"]
        assert isinstance(block["size"], int)
        assert block["size"] > 0


def test_manifest_block_order(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/manifest",
        admin_credential["token"],
    )

    assert code == 200

    data = json_body(body)

    indexes = [
        block["index"]
        for block in data["blocks"]
    ]

    assert indexes == sorted(indexes)

    assert indexes == list(
        range(len(indexes))
    )


def test_metadata_deleted_object(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "DELETE",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}",
        admin_credential["token"],
    )

    assert code in (200, 204), body.decode(
        errors="replace"
    )

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/metadata",
        admin_credential["token"],
    )

    assert code == 404

    data = json_body(body)

    assert data["error"]["code"] == "OBJECT_NOT_FOUND"


def test_manifest_deleted_object(
    admin_credential,
    object_fixture,
):
    object_id = object_fixture["object_id"]
    namespace = object_fixture["namespace"]

    code, _, body = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/"
        f"{object_id}/manifest",
        admin_credential["token"],
    )

    assert code == 404

    data = json_body(body)

    assert data["error"]["code"] in {
        "MANIFEST_NOT_FOUND",
        "MANIFEST_UNAVAILABLE",
        "OBJECT_NOT_FOUND",
    }
