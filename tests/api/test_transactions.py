from __future__ import annotations

import json
import sqlite3
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
):
    headers = {
        "Accept": "application/json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        BASE_URL + path,
        method=method,
        headers=headers,
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


# ============================================================
# FIXTURE — ADMIN
# ============================================================

@pytest.fixture
def transaction_samples():
    from node.registry import (
        connect,
        create_transaction,
        create_transaction_journal,
    )

    transaction_id = unique_name(
        "pytest-api-prepared"
    )

    object_id = unique_name(
        "pytest-api-prepared-object"
    )

    namespace = unique_name(
        "pytest-api-prepared-namespace"
    )

    create_transaction(
        transaction_id=transaction_id,
        object_id=object_id,
        namespace=namespace,
        operation="PUT",
        state="PREPARED",
        metadata={
            "test": "api_transaction_fixture",
        },
    )

    create_transaction_journal(
        transaction_id=transaction_id,
        phase="INTENT",
        resources={
            "object_id": object_id,
            "namespace": namespace,
            "operation": "PUT",
        },
    )

    yield {
        "transaction_id": transaction_id,
        "object_id": object_id,
        "namespace": namespace,
    }

    conn = connect()

    try:
        conn.execute(
            "DELETE FROM transactions WHERE transaction_id = ?",
            (transaction_id,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def admin_credential():
    credential_id = unique_name(
        "pytest-transaction-admin"
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name(
            "pytest-transaction-admin-identity"
        ),
        role="ADMIN",
    )

    yield credential

    revoke_api_credential_by_id(
        credential_id
    )


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_transaction_from_db(
    transaction_id: str,
):
    conn = sqlite3.connect(
        "data/registry.db"
    )

    row = conn.execute(
        """
        SELECT
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at,
            error,
            metadata,
            idempotency_key,
            request_fingerprint
        FROM transactions
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    ).fetchone()

    conn.close()

    return row


def get_journal_from_db(
    transaction_id: str,
):
    conn = sqlite3.connect(
        "data/registry.db"
    )

    row = conn.execute(
        """
        SELECT
            transaction_id,
            phase,
            commit_marker,
            resources,
            verified,
            created_at,
            updated_at
        FROM transaction_journal
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    ).fetchone()

    conn.close()

    return row


def get_sample_transaction(
    state: str,
):
    conn = sqlite3.connect(
        "data/registry.db"
    )

    row = conn.execute(
        """
        SELECT
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at
        FROM transactions
        WHERE state = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (state,),
    ).fetchone()

    conn.close()

    return row


# ============================================================
# 01 — LIST SUCCESS
# ============================================================

def test_transaction_list_success(
    admin_credential,
):
    status, headers, body = http_request(
        "GET",
        "/transactions",
        admin_credential["token"],
    )

    assert status == 200
    assert headers.get("content-type", "").startswith(
        "application/json"
    )

    data = json_body(body)

    assert isinstance(data, dict)
    assert isinstance(
        data["transactions"],
        list,
    )
    assert isinstance(
        data["count"],
        int,
    )
    assert data["count"] == len(
        data["transactions"]
    )


# ============================================================
# 02 — GET SUCCESS
# ============================================================

def test_transaction_get_success(
    admin_credential,
):
    sample = get_sample_transaction(
        "COMMITTED"
    )

    assert sample is not None

    transaction_id = sample[0]

    status, _, body = http_request(
        "GET",
        f"/transactions/{transaction_id}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["transaction_id"] == sample[0]
    assert data["object_id"] == sample[1]
    assert data["namespace"] == sample[2]
    assert data["operation"] == sample[3]
    assert data["state"] == sample[4]
    assert data["created_at"] == sample[5]
    assert data["updated_at"] == sample[6]


# ============================================================
# 03 — LIST REQUIRES AUTHENTICATION
# ============================================================

def test_transaction_list_requires_authentication():
    status, _, body = http_request(
        "GET",
        "/transactions",
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] == "AUTH_REQUIRED"


# ============================================================
# 04 — GET REQUIRES AUTHENTICATION
# ============================================================

def test_transaction_get_requires_authentication():
    status, _, body = http_request(
        "GET",
        "/transactions/does-not-exist",
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] == "AUTH_REQUIRED"


# ============================================================
# 05 — AUTHORIZATION
# ============================================================

def test_transaction_list_requires_node_manage():
    credential_id = unique_name(
        "pytest-transaction-reader"
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name(
            "pytest-transaction-reader-identity"
        ),
        role="READER",
    )

    try:
        status, _, body = http_request(
            "GET",
            "/transactions",
            credential["token"],
        )

        assert status == 403

        data = json_body(body)

        assert data["error"]["code"] in {
            "PERMISSION_DENIED",
            "AUTH_FORBIDDEN",
            "AUTHZ_DENIED",
        }

    finally:
        revoke_api_credential_by_id(
            credential_id
        )


def test_transaction_get_requires_node_manage():
    credential_id = unique_name(
        "pytest-transaction-reader"
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id=unique_name(
            "pytest-transaction-reader-identity"
        ),
        role="READER",
    )

    try:
        status, _, body = http_request(
            "GET",
            "/transactions/does-not-exist",
            credential["token"],
        )

        assert status == 403

        data = json_body(body)

        assert data["error"]["code"] in {
            "PERMISSION_DENIED",
            "AUTH_FORBIDDEN",
            "AUTHZ_DENIED",
        }

    finally:
        revoke_api_credential_by_id(
            credential_id
        )


# ============================================================
# 06 — NOT FOUND
# ============================================================

def test_transaction_not_found(
    admin_credential,
):
    transaction_id = unique_name(
        "pytest-nonexistent-transaction"
    )

    status, _, body = http_request(
        "GET",
        f"/transactions/{transaction_id}",
        admin_credential["token"],
    )

    assert status == 404

    data = json_body(body)

    assert data["error"]["code"] == (
        "TRANSACTION_NOT_FOUND"
    )


# ============================================================
# 07 — RESPONSE CONTRACT
# ============================================================

def test_transaction_response_contract(
    admin_credential,
):
    sample = get_sample_transaction(
        "COMMITTED"
    )

    assert sample is not None

    status, _, body = http_request(
        "GET",
        f"/transactions/{sample[0]}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    required = {
        "transaction_id",
        "object_id",
        "namespace",
        "operation",
        "state",
        "created_at",
        "updated_at",
    }

    assert required.issubset(
        data.keys()
    )

    assert isinstance(
        data["transaction_id"],
        str,
    )
    assert isinstance(
        data["operation"],
        str,
    )
    assert isinstance(
        data["state"],
        str,
    )
    assert isinstance(
        data["created_at"],
        str,
    )
    assert isinstance(
        data["updated_at"],
        str,
    )


# ============================================================
# 08 — COMMITTED
# ============================================================

def test_transaction_committed(
    admin_credential,
):
    sample = get_sample_transaction(
        "COMMITTED"
    )

    assert sample is not None

    status, _, body = http_request(
        "GET",
        f"/transactions/{sample[0]}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["state"] == "COMMITTED"


# ============================================================
# 09 — PREPARED
# ============================================================

def test_transaction_prepared(
    admin_credential,
    transaction_samples,
):
    sample = get_sample_transaction(
        "PREPARED"
    )

    assert sample is not None

    status, _, body = http_request(
        "GET",
        f"/transactions/{sample[0]}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["state"] == "PREPARED"


# ============================================================
# 10 — ROLLBACK
# ============================================================

def test_transaction_rollback(
    admin_credential,
):
    sample = get_sample_transaction(
        "ROLLBACK"
    )

    assert sample is not None

    status, _, body = http_request(
        "GET",
        f"/transactions/{sample[0]}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["state"] == "ROLLBACK"


# ============================================================
# 11 — TRANSACTION ↔ JOURNAL
# ============================================================

@pytest.mark.parametrize(
    "state",
    [
        "COMMITTED",
        "PREPARED",
        "ROLLBACK",
    ],
)
def test_transaction_journal_relation(
    admin_credential,
    transaction_samples,
    state,
):
    sample = get_sample_transaction(
        state
    )

    assert sample is not None

    transaction_id = sample[0]

    status, _, body = http_request(
        "GET",
        f"/transactions/{transaction_id}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["transaction_id"] == (
        transaction_id
    )

    journal = get_journal_from_db(
        transaction_id
    )

    if journal is None:
        # A transaction without journal is a
        # valid recovery/audit condition.
        assert state in {
            "PREPARED",
            "ROLLBACK",
        }
        return

    assert journal[0] == transaction_id
    assert isinstance(
        journal[1],
        str,
    )
    assert journal[2] in (0, 1)
    assert journal[4] in (0, 1)


# ============================================================
# 12 — OBJECT / NAMESPACE / OPERATION
# ============================================================

def test_transaction_identity_fields(
    admin_credential,
):
    sample = get_sample_transaction(
        "COMMITTED"
    )

    assert sample is not None

    transaction_id = sample[0]

    status, _, body = http_request(
        "GET",
        f"/transactions/{transaction_id}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["transaction_id"] == sample[0]
    assert data["object_id"] == sample[1]
    assert data["namespace"] == sample[2]
    assert data["operation"] == sample[3]


# ============================================================
# 13 — TIMESTAMPS
# ============================================================

def test_transaction_timestamps(
    admin_credential,
):
    sample = get_sample_transaction(
        "COMMITTED"
    )

    assert sample is not None

    status, _, body = http_request(
        "GET",
        f"/transactions/{sample[0]}",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    assert data["created_at"]
    assert data["updated_at"]

    assert data["updated_at"] >= (
        data["created_at"]
    )


# ============================================================
# 14 — LIST CONTAINS REAL DATABASE TRANSACTION
# ============================================================

def test_transaction_list_contains_database_record(
    admin_credential,
):
    sample = get_sample_transaction(
        "COMMITTED"
    )

    assert sample is not None

    status, _, body = http_request(
        "GET",
        "/transactions",
        admin_credential["token"],
    )

    assert status == 200

    data = json_body(body)

    ids = {
        item["transaction_id"]
        for item in data["transactions"]
    }

    assert sample[0] in ids


# ============================================================
# 15 — OPENAPI CONTRACT
# ============================================================

def test_transaction_openapi_contract():
    status, _, body = http_request(
        "GET",
        "/openapi.json",
    )

    assert status == 200

    data = json_body(body)

    paths = data["paths"]

    assert "/api/v1/transactions" in paths
    assert "/api/v1/transactions/{transaction_id}" in paths

    list_operation = paths[
        "/api/v1/transactions"
    ]["get"]

    get_operation = paths[
        "/api/v1/transactions/{transaction_id}"
    ]["get"]

    assert (
        list_operation["operationId"]
        == "list_transactions_api_v1_transactions_get"
    )

    assert (
        get_operation["operationId"]
        == "get_transaction_api_v1_transactions__transaction_id__get"
    )

    assert "200" in list_operation["responses"]
    assert "200" in get_operation["responses"]

    assert (
        "TransactionListResponse"
        in json.dumps(list_operation)
    )

    assert (
        "TransactionResponse"
        in json.dumps(get_operation)
    )
