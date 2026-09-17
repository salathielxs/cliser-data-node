import json
import urllib.error
import urllib.request
import uuid

from node.credential_manager import (
    create_api_credential,
    revoke_api_credential_by_id,
)
from node.metrics import storage_metrics


BASE_URL = "http://127.0.0.1:8000/api/v1"


def request(path, authorization=None):
    headers = {
        "Accept": "application/json",
    }

    if authorization:
        headers["Authorization"] = authorization

    request_obj = urllib.request.Request(
        BASE_URL + path,
        headers=headers,
        method="GET",
    )

    try:
        with urllib.request.urlopen(
            request_obj,
            timeout=10,
        ) as response:
            return (
                response.status,
                json.loads(
                    response.read().decode("utf-8")
                ),
            )

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw

        return exc.code, payload


def test_api_metrics_matches_internal_metrics():
    credential_id = (
        "pytest-metrics-admin-"
        + uuid.uuid4().hex[:12]
    )

    credential = create_api_credential(
        credential_id=credential_id,
        identity_id="pytest-metrics-admin",
        role="ADMIN",
    )

    try:
        internal = storage_metrics()

        status, api = request(
            "/metrics",
            authorization=f"Bearer {credential['token']}",
        )

        assert status == 200

        expected_keys = {
            "objects",
            "direct",
            "block_objects",
            "blocks",
            "deduplication",
            "capacity",
        }

        assert set(api.keys()) == expected_keys

        assert api["objects"] == internal["objects"]
        assert api["direct"] == internal["direct"]
        assert api["block_objects"] == internal["block_objects"]
        assert api["blocks"] == internal["blocks"]
        assert api["deduplication"] == internal["deduplication"]
        assert api["capacity"] == internal["capacity"]

    finally:
        revoke_api_credential_by_id(
            credential_id
        )
