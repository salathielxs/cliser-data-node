import sys
from pathlib import Path

# Bootstrap explícito do projeto para Termux/pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(
    "/data/data/com.termux/files/home/cliser-data-node"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import hashlib
import json
import urllib.error
import urllib.request
import uuid

import pytest

from node.credential_manager import (
    create_api_credential,
    revoke_api_credential_by_id,
)
# Carrega api/config.py diretamente.
# Evita conflito de resolução de módulos durante a coleta do pytest/Termux.
import importlib.util

CONFIG_PATH = PROJECT_ROOT / "api" / "config.py"

_config_spec = importlib.util.spec_from_file_location(
    "cliser_test_config",
    CONFIG_PATH,
)

if _config_spec is None or _config_spec.loader is None:
    raise RuntimeError(
        f"Não foi possível carregar {CONFIG_PATH}"
    )

_config = importlib.util.module_from_spec(_config_spec)
_config_spec.loader.exec_module(_config)

MAX_FILENAME_BYTES = _config.MAX_FILENAME_BYTES
MAX_OBJECT_SIZE_BYTES = _config.MAX_OBJECT_SIZE_BYTES
MAX_UPLOAD_SIZE_BYTES = _config.MAX_UPLOAD_SIZE_BYTES

BASE_URL = "http://127.0.0.1:8000/api/v1"


def request(
    path,
    authorization=None,
    method="GET",
    body=None,
    headers=None,
):
    h = {
        "Accept": "application/json",
    }

    if authorization:
        h["Authorization"] = f"Bearer {authorization}"

    if headers:
        h.update(headers)

    data = body

    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers=h,
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")

            if "application/json" in content_type:
                payload = json.loads(raw.decode("utf-8"))
            else:
                payload = raw

            return response.status, payload, response.headers

    except urllib.error.HTTPError as exc:
        raw = exc.read()

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = raw

        return exc.code, payload, exc.headers


def multipart_body(
    field_name,
    filename,
    content,
):
    boundary = (
        "----CLISERUpload"
        + uuid.uuid4().hex
    ).encode()

    parts = []

    parts.append(
        b"--" + boundary + b"\r\n"
        + (
            f'Content-Disposition: form-data; '
            f'name="{field_name}"; '
            f'filename="{filename}"\r\n'
        ).encode()
        + b"Content-Type: application/octet-stream\r\n"
        + b"\r\n"
        + content
        + b"\r\n"
    )

    parts.append(
        b"--" + boundary + b"--\r\n"
    )

    return boundary, b"".join(parts)


def upload(
    namespace,
    token,
    filename="test.txt",
    content=b"CLISER DATA NODE upload test",
):
    boundary, body = multipart_body(
        "file",
        filename,
        content,
    )

    return request(
        f"/namespaces/{namespace}/uploads",
        authorization=token,
        method="POST",
        body=body,
        headers={
            "Content-Type": (
                "multipart/form-data; "
                f"boundary={boundary.decode()}"
            ),
        },
    )


def unique_namespace():
    return "upload_test_" + uuid.uuid4().hex[:12]


@pytest.fixture
def admin():
    credential_id = "UPLOAD-ADMIN-" + uuid.uuid4().hex[:12]
    identity_id = "UPLOAD-IDENTITY-" + uuid.uuid4().hex[:12]

    result = create_api_credential(
        credential_id=credential_id,
        identity_id=identity_id,
        role="ADMIN",
    )

    token = result["token"]
    credential_id = result["credential_id"]

    yield token

    try:
        revoke_api_credential_by_id(credential_id)
    except Exception:
        pass


@pytest.fixture
def namespace(admin):
    name = unique_namespace()

    status, payload, _ = request(
        "/namespaces",
        authorization=admin,
        method="POST",
        body=json.dumps({
            "namespace": name,
        }).encode(),
        headers={
            "Content-Type": "application/json",
        },
    )

    assert status == 201, payload

    return name


def test_upload_success(admin, namespace):
    content = b"CLISER upload integration test"

    status, payload, _ = upload(
        namespace,
        admin,
        "hello.txt",
        content,
    )

    assert status == 201, payload
    assert payload["namespace"] == namespace
    assert payload["filename"] == "hello.txt"
    assert payload["size"] == len(content)
    assert payload["status"] in {
        "ACTIVE",
        "COMMITTED",
    }
    assert payload["object_id"]
    assert payload["content_hash"]

    expected_hash = hashlib.sha256(content).hexdigest()

    assert payload["content_hash"] == expected_hash


def test_upload_without_auth(namespace):
    boundary, body = multipart_body(
        "file",
        "noauth.txt",
        b"unauthorized",
    )

    status, payload, _ = request(
        f"/namespaces/{namespace}/uploads",
        method="POST",
        body=body,
        headers={
            "Content-Type": (
                "multipart/form-data; "
                f"boundary={boundary.decode()}"
            ),
        },
    )

    assert status == 401
    assert payload["error"]["code"] in {
        "AUTH_REQUIRED",
        "AUTH_INVALID",
    }


def test_upload_empty_file(admin, namespace):
    status, payload, _ = upload(
        namespace,
        admin,
        "empty.txt",
        b"",
    )

    assert status == 400
    assert payload["error"]["code"] in {
        "UPLOAD_FAILED",
        "UPLOAD_ERROR",
    }


def test_upload_nonexistent_namespace(admin):
    namespace = "does_not_exist_" + uuid.uuid4().hex

    status, payload, _ = upload(
        namespace,
        admin,
        "missing.txt",
        b"test",
    )

    assert status == 404
    assert payload["error"]["code"] == "NAMESPACE_NOT_FOUND"


def test_filename_too_large(admin, namespace):
    filename_bytes = (
        b"a" * (MAX_FILENAME_BYTES + 1)
    )

    filename = filename_bytes.decode(
        "ascii"
    )

    status, payload, _ = upload(
        namespace,
        admin,
        filename,
        b"test",
    )

    assert status == 413, payload
    assert payload["error"]["code"] == "FILENAME_TOO_LARGE"


def test_object_too_large(admin, namespace):
    content = b"x" * (
        MAX_OBJECT_SIZE_BYTES + 1
    )

    status, payload, _ = upload(
        namespace,
        admin,
        "too-large-object.bin",
        content,
    )

    assert status == 413, payload
    assert payload["error"]["code"] == "OBJECT_TOO_LARGE"


def test_upload_transport_limit(admin, namespace):
    content = b"x" * (
        MAX_UPLOAD_SIZE_BYTES + 1
    )

    status, payload, _ = upload(
        namespace,
        admin,
        "too-large-upload.bin",
        content,
    )

    # O limite lógico de objeto é menor que o limite
    # de transporte; portanto a API pode rejeitar
    # primeiro como OBJECT_TOO_LARGE.
    assert status == 413, payload
    assert payload["error"]["code"] in {
        "OBJECT_TOO_LARGE",
        "UPLOAD_TOO_LARGE",
    }
