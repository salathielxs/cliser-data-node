import json
import urllib.error
import urllib.request


BASE_URL = "http://127.0.0.1:8000/api/v1"


def request(path):
    req = urllib.request.Request(
        BASE_URL + path,
        method="GET",
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"raw": body}

        return exc.code, data


def test_health_live():
    status, body = request("/health/live")

    assert status == 200
    assert body["status"] == "ok"
    assert body["service"] == "cliser-data-node"
    assert body["api_version"] == "v1"


def test_health():
    status, body = request("/health")

    assert status == 200
    assert body["service"] == "cliser-data-node"
    assert "status" in body
    assert "checks" in body


def test_health_ready():
    status, body = request("/health/ready")

    assert status in (200, 503)
    assert body["service"] == "cliser-data-node"
    assert "status" in body
    assert "checks" in body
