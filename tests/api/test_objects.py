import base64
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


def request(
    path,
    authorization=None,
    method="GET",
    body=None,
    headers=None,
):
    request_headers = {
        "Accept": "application/json",
    }

    if authorization:
        request_headers["Authorization"] = f"Bearer {authorization}"

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
            raw = response.read().decode()

            try:
                payload = json.loads(raw)
            except Exception:
                payload = raw

            return response.status, payload

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()

        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw

        return exc.code, payload


def error_code(body):
    return body.get("error", {}).get("code")


def unique_name(prefix):
    return prefix + "-" + uuid.uuid4().hex[:12]


def encoded(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest.fixture
def admin_credential():
    credential_id = unique_name("pytest-object-admin")

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name("pytest-object-admin-identity"),
        role="ADMIN",
    )

    yield credential

    revoke_api_credential_by_id(credential_id)


@pytest.fixture
def namespace_with_admin(admin_credential):
    namespace = unique_name("pytest-object")

    status, body = request(
        "/namespaces",
        authorization=admin_credential["token"],
        method="POST",
        body={
            "namespace": namespace,
            "quota_bytes": 1024 * 1024,
        },
    )

    assert status == 201, body

    return namespace


@pytest.fixture
def writer_credential(namespace_with_admin):
    credential_id = unique_name("pytest-object-writer")

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name("pytest-object-writer-identity"),
        role="WRITER",
        namespace=namespace_with_admin,
    )

    yield credential

    revoke_api_credential_by_id(credential_id)


@pytest.fixture
def reader_credential(namespace_with_admin):
    credential_id = unique_name("pytest-object-reader")

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name("pytest-object-reader-identity"),
        role="READER",
        namespace=namespace_with_admin,
    )

    yield credential

    revoke_api_credential_by_id(credential_id)


# ============================================================
# CREATE
# ============================================================


def test_create_object_requires_auth(namespace_with_admin):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        method="POST",
        body={"data": encoded("hello")},
    )

    assert status == 401
    assert error_code(body) == "AUTH_REQUIRED"


def test_reader_cannot_create_object(
    namespace_with_admin,
    reader_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=reader_credential["token"],
        method="POST",
        body={"data": encoded("hello")},
    )

    assert status == 403
    assert error_code(body) == "AUTHZ_DENIED"


def test_writer_can_create_object(
    namespace_with_admin,
    writer_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("hello world")},
    )

    assert status == 201, body
    assert body["object_id"]
    assert body["namespace"] == namespace_with_admin
    assert body["size"] == len("hello world")
    assert body["content_hash"]
    assert body["status"]


def test_admin_can_create_object(
    namespace_with_admin,
    admin_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=admin_credential["token"],
        method="POST",
        body={"data": encoded("admin object")},
    )

    assert status == 201, body
    assert body["object_id"]
    assert body["namespace"] == namespace_with_admin


def test_create_object_invalid_base64(
    namespace_with_admin,
    writer_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": "!!!not-base64!!!"},
    )

    assert status == 400
    assert error_code(body) == "OBJECT_CREATE_FAILED"


def test_create_object_empty_data(
    namespace_with_admin,
    writer_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": ""},
    )

    assert status == 422
    assert error_code(body) == "VALIDATION_ERROR"


def test_create_object_missing_data(
    namespace_with_admin,
    writer_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={},
    )

    assert status == 422
    assert error_code(body) == "VALIDATION_ERROR"


def test_create_object_nonexistent_namespace(admin_credential):
    namespace = unique_name("pytest-object-missing")

    status, body = request(
        f"/namespaces/{namespace}/objects",
        authorization=admin_credential["token"],
        method="POST",
        body={"data": encoded("hello")},
    )

    assert status == 404, body
    assert error_code(body) == "NAMESPACE_NOT_FOUND"


# ============================================================
# GET
# ============================================================


def test_get_object(
    namespace_with_admin,
    writer_credential,
):
    status, created = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("read test")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}",
        authorization=writer_credential["token"],
    )

    assert status == 200, body
    assert body["object_id"] == object_id
    assert body["namespace"] == namespace_with_admin
    assert body["size"] == len("read test")
    assert body["content_hash"]
    assert body["status"]


def test_get_nonexistent_object(
    namespace_with_admin,
    reader_credential,
):
    object_id = unique_name("missing-object")

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}",
        authorization=reader_credential["token"],
    )

    assert status == 404
    assert error_code(body) == "OBJECT_NOT_FOUND"


# ============================================================
# LIST
# ============================================================


def test_list_objects_requires_auth(namespace_with_admin):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
    )

    assert status == 401
    assert error_code(body) == "AUTH_REQUIRED"


def test_list_objects(
    namespace_with_admin,
    writer_credential,
):
    status, created = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("list test")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
    )

    assert status == 200, body
    assert body["namespace"] == namespace_with_admin
    assert body["count"] >= 1

    ids = {
        item["object_id"]
        for item in body["objects"]
    }

    assert object_id in ids


# ============================================================
# NAMESPACE ISOLATION
# ============================================================


def test_object_isolation_between_namespaces(admin_credential):
    namespace_a = unique_name("pytest-object-a")
    namespace_b = unique_name("pytest-object-b")

    for namespace in (namespace_a, namespace_b):
        status, body = request(
            "/namespaces",
            authorization=admin_credential["token"],
            method="POST",
            body={
                "namespace": namespace,
                "quota_bytes": 1024 * 1024,
            },
        )

        assert status == 201, body

    status, created = request(
        f"/namespaces/{namespace_a}/objects",
        authorization=admin_credential["token"],
        method="POST",
        body={"data": encoded("private namespace A")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_b}/objects/{object_id}",
        authorization=admin_credential["token"],
    )

    assert status == 404
    assert error_code(body) == "OBJECT_NOT_FOUND"


def test_object_cannot_be_deleted_from_other_namespace(
    admin_credential,
):
    namespace_a = unique_name("pytest-delete-a")
    namespace_b = unique_name("pytest-delete-b")

    for namespace in (namespace_a, namespace_b):
        status, body = request(
            "/namespaces",
            authorization=admin_credential["token"],
            method="POST",
            body={
                "namespace": namespace,
                "quota_bytes": 1024 * 1024,
            },
        )

        assert status == 201, body

    status, created = request(
        f"/namespaces/{namespace_a}/objects",
        authorization=admin_credential["token"],
        method="POST",
        body={"data": encoded("protected")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_b}/objects/{object_id}",
        authorization=admin_credential["token"],
        method="DELETE",
    )

    assert status == 404
    assert error_code(body) == "OBJECT_NOT_FOUND"

    status, body = request(
        f"/namespaces/{namespace_a}/objects/{object_id}",
        authorization=admin_credential["token"],
    )

    assert status == 200, body


# ============================================================
# VERIFY
# ============================================================


def test_verify_object(
    namespace_with_admin,
    writer_credential,
):
    status, created = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("integrity test")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}/verify",
        authorization=writer_credential["token"],
    )

    assert status == 200, body
    assert body["object_id"] == object_id
    assert body["valid"] is True
    assert body["status"]


def test_verify_nonexistent_object(
    namespace_with_admin,
    reader_credential,
):
    object_id = unique_name("missing-verify")

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}/verify",
        authorization=reader_credential["token"],
    )

    assert status == 404
    assert error_code(body) == "OBJECT_NOT_FOUND"


# ============================================================
# DELETE
# ============================================================


def test_reader_cannot_delete_object(
    namespace_with_admin,
    writer_credential,
    reader_credential,
):
    status, created = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("delete authorization")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}",
        authorization=reader_credential["token"],
        method="DELETE",
    )

    assert status == 403
    assert error_code(body) == "AUTHZ_DENIED"


def test_delete_object(
    namespace_with_admin,
    writer_credential,
):
    status, created = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("delete test")},
    )

    assert status == 201, created

    object_id = created["object_id"]

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}",
        authorization=writer_credential["token"],
        method="DELETE",
    )

    assert status == 200, body
    assert body["object_id"] == object_id
    assert body["deleted"] is True

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}",
        authorization=writer_credential["token"],
    )

    assert status == 404
    assert error_code(body) == "OBJECT_NOT_FOUND"


def test_delete_nonexistent_object(
    namespace_with_admin,
    writer_credential,
):
    object_id = unique_name("missing-delete")

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects/{object_id}",
        authorization=writer_credential["token"],
        method="DELETE",
    )

    assert status == 404
    assert error_code(body) == "OBJECT_NOT_FOUND"


# ============================================================
# REVOCATION
# ============================================================


def test_revoked_credential_cannot_access_objects(
    namespace_with_admin,
    writer_credential,
):
    token = writer_credential["token"]
    credential_id = writer_credential["credential_id"]

    revoke_api_credential_by_id(credential_id)

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=token,
    )

    assert status == 401
    assert error_code(body) == "AUTH_REVOKED"


# ============================================================
# IDEMPOTENCY — 14.24.14
# ============================================================


def test_create_object_idempotency_replays_same_response(
    namespace_with_admin,
    writer_credential,
):
    key = unique_name("idem-replay")
    data = encoded("idempotent payload")

    path = f"/namespaces/{namespace_with_admin}/objects"

    status1, body1 = request(
        path,
        authorization=writer_credential["token"],
        method="POST",
        body={"data": data},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status1 == 201, body1
    assert body1["object_id"]
    assert body1["content_hash"]

    status2, body2 = request(
        path,
        authorization=writer_credential["token"],
        method="POST",
        body={"data": data},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status2 == 201, body2
    assert body2 == body1


def test_create_object_idempotency_conflict_on_different_payload(
    namespace_with_admin,
    writer_credential,
):
    key = unique_name("idem-conflict")
    path = f"/namespaces/{namespace_with_admin}/objects"

    status1, body1 = request(
        path,
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("payload-A")},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status1 == 201, body1

    status2, body2 = request(
        path,
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("payload-B")},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status2 == 409, body2
    assert error_code(body2) == "IDEMPOTENCY_KEY_CONFLICT"


def test_create_object_idempotency_creates_only_one_object(
    namespace_with_admin,
    writer_credential,
):
    key = unique_name("idem-single-effect")
    data = encoded("single persistent effect")

    path = f"/namespaces/{namespace_with_admin}/objects"

    status1, body1 = request(
        path,
        authorization=writer_credential["token"],
        method="POST",
        body={"data": data},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status1 == 201, body1

    status2, body2 = request(
        path,
        authorization=writer_credential["token"],
        method="POST",
        body={"data": data},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status2 == 201, body2
    assert body2["object_id"] == body1["object_id"]

    list_status, list_body = request(
        path,
        authorization=writer_credential["token"],
        method="GET",
    )

    assert list_status == 200, list_body

    matching = [
        item
        for item in list_body["objects"]
        if item["object_id"] == body1["object_id"]
    ]

    assert len(matching) == 1


def test_create_object_idempotency_key_too_large(
    namespace_with_admin,
    writer_credential,
):
    key = "K" * 257

    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("too large key")},
        headers={
            "Idempotency-Key": key,
        },
    )

    assert status == 413, body
    assert error_code(body) == "IDEMPOTENCY_KEY_TOO_LARGE"
    assert body["error"]["details"]["max_bytes"] == 256


def test_create_object_empty_idempotency_key(
    namespace_with_admin,
    writer_credential,
):
    status, body = request(
        f"/namespaces/{namespace_with_admin}/objects",
        authorization=writer_credential["token"],
        method="POST",
        body={"data": encoded("empty key")},
        headers={
            "Idempotency-Key": "   ",
        },
    )

    assert status == 400, body
    assert error_code(body) == "OBJECT_CREATE_FAILED"


# ============================================================
# IDEMPOTENCY — CONCURRENCY
# ============================================================


def test_create_object_idempotency_concurrent_same_key(
    namespace_with_admin,
    writer_credential,
):
    from concurrent.futures import ThreadPoolExecutor

    key = unique_name("idem-concurrent")
    data = encoded("concurrent idempotency payload")

    path = f"/namespaces/{namespace_with_admin}/objects"

    def send_request():
        return request(
            path,
            authorization=writer_credential["token"],
            method="POST",
            body={"data": data},
            headers={
                "Idempotency-Key": key,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(send_request)
            for _ in range(2)
        ]

        results = [
            future.result()
            for future in futures
        ]

    statuses = [status for status, _ in results]

    assert all(
        status in {201, 409}
        for status in statuses
    ), results

    successful = [
        body
        for status, body in results
        if status == 201
    ]

    assert len(successful) >= 1

    if len(successful) == 2:
        assert (
            successful[0]["object_id"]
            == successful[1]["object_id"]
        )

    list_status, list_body = request(
        path,
        authorization=writer_credential["token"],
        method="GET",
    )

    assert list_status == 200, list_body

    object_ids = {
        body["object_id"]
        for status, body in results
        if status == 201
    }

    matching = [
        item
        for item in list_body["objects"]
        if item["object_id"] in object_ids
    ]

    assert len(matching) == 1
