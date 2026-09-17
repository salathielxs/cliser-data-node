from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def json_body(body: bytes):
    return json.loads(body.decode())


def request(
    method: str,
    path: str,
    token: str | None = None,
):
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        BASE + path,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
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


def test_health_before_lifecycle():
    status, headers, body = request(
        "GET",
        "/api/v1/health",
    )

    assert status == 200

    data = json_body(body)

    assert isinstance(data, dict)


def test_lifecycle_gc_requires_auth():
    status, headers, body = request(
        "POST",
        "/api/v1/lifecycle/gc",
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] in {
        "AUTH_REQUIRED",
        "AUTH_INVALID",
    }


def test_lifecycle_rebuild_requires_auth():
    status, headers, body = request(
        "POST",
        "/api/v1/lifecycle/rebuild-refcounts",
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] in {
        "AUTH_REQUIRED",
        "AUTH_INVALID",
    }


def test_lifecycle_integrity_requires_auth():
    status, headers, body = request(
        "POST",
        "/api/v1/lifecycle/integrity-check",
    )

    assert status == 401

    data = json_body(body)

    assert data["error"]["code"] in {
        "AUTH_REQUIRED",
        "AUTH_INVALID",
    }


def test_lifecycle_openapi_contract():
    status, headers, body = request(
        "GET",
        "/api/v1/openapi.json",
    )

    assert status == 200

    data = json_body(body)
    paths = data["paths"]

    lifecycle_paths = (
        "/api/v1/lifecycle/gc",
        "/api/v1/lifecycle/rebuild-refcounts",
        "/api/v1/lifecycle/integrity-check",
    )

    for path in lifecycle_paths:
        assert path in paths
        assert "post" in paths[path]

        operation = paths[path]["post"]

        assert "security" in operation

        security_names = set()

        for item in operation["security"]:
            security_names.update(item.keys())

        assert "bearerAuth" in security_names


def test_lifecycle_invalid_token():
    lifecycle_paths = (
        "/api/v1/lifecycle/gc",
        "/api/v1/lifecycle/rebuild-refcounts",
        "/api/v1/lifecycle/integrity-check",
    )

    for path in lifecycle_paths:
        status, headers, body = request(
            "POST",
            path,
            token="invalid-token",
        )

        assert status in {401, 403}

        data = json_body(body)

        assert "error" in data
        assert isinstance(data["error"]["code"], str)
