import json
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000/api/v1"


def request(path, authorization=None):
    headers = {
        "Accept": "application/json",
    }

    if authorization is not None:
        headers["Authorization"] = authorization

    req = urllib.request.Request(
        BASE_URL + path,
        method="GET",
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = body

            return response.status, data

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"raw": body}

        return exc.code, data


def error_code(body):
    return body.get("error", {}).get("code")


def test_auth_required():
    status, body = request("/auth/me")

    assert status == 401
    assert error_code(body) == "AUTH_REQUIRED"


def test_auth_invalid_scheme():
    status, body = request(
        "/auth/me",
        authorization="Basic invalid-credential",
    )

    assert status == 401
    assert error_code(body) == "AUTH_INVALID"


def test_auth_invalid_bearer():
    status, body = request(
        "/auth/me",
        authorization="Bearer invalid-credential",
    )

    assert status == 401
    assert error_code(body) == "AUTH_INVALID"
