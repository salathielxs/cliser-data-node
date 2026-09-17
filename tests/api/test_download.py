from __future__ import annotations

import json
import os
import sys
import uuid
import urllib.error
import urllib.request

import pytest


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


BASE_URL = "http://127.0.0.1:8000"

from node.object_manager import put_object
from node.credential_manager import (
    create_api_credential,
    revoke_api_credential_by_id,
)


def http_request(
    method: str,
    path: str,
    token: str | None = None,
    body: bytes | None = None,
    content_type: str | None = None,
):
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if content_type:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return (
                response.status,
                response.read(),
                dict(response.headers),
            )

    except urllib.error.HTTPError as exc:
        return (
            exc.code,
            exc.read(),
            dict(exc.headers),
        )


def json_body(data: bytes):
    if not data:
        return {}

    return json.loads(data.decode("utf-8"))


def create_namespace(name: str, token: str):
    status, body, _ = http_request(
        "POST",
        "/api/v1/namespaces",
        token=token,
        body=json.dumps({
            "namespace": name,
        }).encode(),
        content_type="application/json",
    )

    assert status in (200, 201), body


@pytest.fixture
def admin():
    credential_id = "DOWNLOAD-ADMIN-" + uuid.uuid4().hex[:12]
    identity_id = "DOWNLOAD-IDENTITY-" + uuid.uuid4().hex[:12]

    result = create_api_credential(
        credential_id=credential_id,
        identity_id=identity_id,
        role="ADMIN",
    )

    token = result["token"]

    yield token

    try:
        revoke_api_credential_by_id(credential_id)
    except Exception:
        pass


@pytest.fixture
def namespace(admin):
    name = "download_test_" + uuid.uuid4().hex[:12]
    create_namespace(name, admin)
    return name


def create_test_object(namespace: str, content: bytes, token: str):
    import base64

    payload = {
        "data": base64.b64encode(content).decode("ascii"),
        "filename": "download-test.bin",
    }

    status, body, _ = http_request(
        "POST",
        f"/api/v1/namespaces/{namespace}/objects",
        token=token,
        body=json.dumps(payload).encode(),
        content_type="application/json",
    )

    assert status in (200, 201), body

    result = json_body(body)

    return result


def test_download_success(admin, namespace):
    content = b"CLISER DATA NODE DOWNLOAD TEST"

    result = create_test_object(namespace, content, admin)
    object_id = result["object_id"]
    content_hash = result["content_hash"]

    status, body, headers = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/{object_id}/download",
        token=admin,
    )

    assert status == 200
    assert body == content
    content_length = next(
        int(value)
        for key, value in headers.items()
        if key.lower() == "content-length"
    )
    assert content_length == len(content)
    object_id_header = next(
        value
        for key, value in headers.items()
        if key.lower() == "x-object-id"
    )

    content_hash_header = next(
        value
        for key, value in headers.items()
        if key.lower() == "x-content-hash"
    )

    assert object_id_header == object_id
    assert content_hash_header == content_hash


def test_download_binary_content(admin, namespace):
    content = bytes(range(256)) * 4

    result = create_test_object(namespace, content, admin)
    object_id = result["object_id"]

    status, body, headers = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/{object_id}/download",
        token=admin,
    )

    assert status == 200
    assert body == content
    assert len(body) == 1024


def test_download_without_auth(namespace):
    fake_object_id = uuid.uuid4().hex

    status, body, _ = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/{fake_object_id}/download",
    )

    assert status == 401

    payload = json_body(body)
    assert payload["error"]["code"] == "AUTH_REQUIRED"


def test_download_nonexistent_object(admin, namespace):
    object_id = uuid.uuid4().hex

    status, body, _ = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/{object_id}/download",
        token=admin,
    )

    assert status == 404

    payload = json_body(body)
    assert payload["error"]["code"] == "OBJECT_NOT_FOUND"


def test_download_nonexistent_namespace(admin):
    namespace = "download_missing_" + uuid.uuid4().hex[:12]
    object_id = uuid.uuid4().hex

    status, body, _ = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/{object_id}/download",
        token=admin,
    )

    assert status == 404

    payload = json_body(body)
    assert payload["error"]["code"] == "NAMESPACE_NOT_FOUND"


def test_download_object_from_other_namespace(admin):
    namespace_a = "download_a_" + uuid.uuid4().hex[:12]
    namespace_b = "download_b_" + uuid.uuid4().hex[:12]

    create_namespace(namespace_a, admin)
    create_namespace(namespace_b, admin)

    content = b"PRIVATE-NAMESPACE-DATA"

    result = create_test_object(namespace_a, content, admin)
    object_id = result["object_id"]

    status, body, _ = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace_b}/objects/{object_id}/download",
        token=admin,
    )

    assert status == 403

    payload = json_body(body)
    assert payload["error"]["code"] == "OBJECT_NAMESPACE_ERROR"


def test_download_deleted_object(admin, namespace):
    content = b"DELETE-DOWNLOAD-TEST"

    result = create_test_object(namespace, content, admin)
    object_id = result["object_id"]

    status, body, _ = http_request(
        "DELETE",
        f"/api/v1/namespaces/{namespace}/objects/{object_id}",
        token=admin,
    )

    assert status == 200, body

    status, body, _ = http_request(
        "GET",
        f"/api/v1/namespaces/{namespace}/objects/{object_id}/download",
        token=admin,
    )

    assert status == 404

    payload = json_body(body)
    assert payload["error"]["code"] == "OBJECT_NOT_FOUND"
