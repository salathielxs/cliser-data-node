from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

from api.rate_limit import SlidingWindowRateLimiter
from api.rate_limit_policy import get_rate_limit_policy


BASE_URL = "http://127.0.0.1:8000/api/v1"


def request(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
):
    req = urllib.request.Request(
        BASE_URL + path,
        method=method,
        headers=headers or {},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            return response.status, dict(response.headers), payload

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        payload = json.loads(raw) if raw else {}
        return exc.code, dict(exc.headers), payload


def header_value(
    headers: dict[str, str],
    name: str,
):
    wanted = name.lower()

    for key, value in headers.items():
        if key.lower() == wanted:
            return value

    return None


def test_rate_limit_policy_read():
    policy = get_rate_limit_policy("GET")

    assert policy.operation == "READ"
    assert policy.limit == 120
    assert policy.window_seconds == 60


def test_rate_limit_policy_write():
    policy = get_rate_limit_policy("POST")

    assert policy.operation == "WRITE"
    assert policy.limit == 60
    assert policy.window_seconds == 60


def test_sliding_window_allows_until_limit():
    limiter = SlidingWindowRateLimiter()

    first = limiter.check(
        key="pytest-read",
        limit=3,
        window_seconds=60,
    )

    second = limiter.check(
        key="pytest-read",
        limit=3,
        window_seconds=60,
    )

    third = limiter.check(
        key="pytest-read",
        limit=3,
        window_seconds=60,
    )

    assert first.allowed is True
    assert first.remaining == 2

    assert second.allowed is True
    assert second.remaining == 1

    assert third.allowed is True
    assert third.remaining == 0


def test_sliding_window_blocks_after_limit():
    limiter = SlidingWindowRateLimiter()

    for _ in range(3):
        result = limiter.check(
            key="pytest-block",
            limit=3,
            window_seconds=60,
        )

        assert result.allowed is True

    blocked = limiter.check(
        key="pytest-block",
        limit=3,
        window_seconds=60,
    )

    assert blocked.allowed is False
    assert blocked.limit == 3
    assert blocked.remaining == 0
    assert blocked.retry_after >= 1


def test_sliding_window_isolated_by_key():
    limiter = SlidingWindowRateLimiter()

    assert limiter.check(
        key="client-a",
        limit=1,
        window_seconds=60,
    ).allowed is True

    assert limiter.check(
        key="client-a",
        limit=1,
        window_seconds=60,
    ).allowed is False

    assert limiter.check(
        key="client-b",
        limit=1,
        window_seconds=60,
    ).allowed is True


def test_sliding_window_clear():
    limiter = SlidingWindowRateLimiter()

    limiter.check(
        key="pytest-clear",
        limit=1,
        window_seconds=60,
    )

    assert limiter.size() == 1

    limiter.clear()

    assert limiter.size() == 0


def test_http_rate_limit_headers_are_present():
    status, headers, payload = request(
        "GET",
        f"/health?rate_test={uuid.uuid4()}",
    )

    assert status == 200
    assert payload.get("status") in {"HEALTHY", "WARNING", "CRITICAL"}

    assert header_value(
        headers,
        "X-RateLimit-Limit",
    ) == "120"

    assert header_value(
        headers,
        "X-RateLimit-Remaining",
    ) is not None
