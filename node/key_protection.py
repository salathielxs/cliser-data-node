from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "crypto_identity.json"
)

VERSION = 1
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32


class KeyProtectionError(Exception):
    pass


def _b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64_decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def derive_key(password: str, salt: bytes) -> bytes:
    if not isinstance(password, str) or not password:
        raise KeyProtectionError("Senha inválida.")

    if not isinstance(salt, bytes) or len(salt) != SALT_SIZE:
        raise KeyProtectionError("Salt inválido.")

    kdf = Scrypt(
        salt=salt,
        length=KEY_SIZE,
        n=2**14,
        r=8,
        p=1,
    )

    return kdf.derive(password.encode("utf-8"))


def encrypt_private_key(
    private_key: bytes,
    password: str,
) -> dict:

    if not isinstance(private_key, bytes) or not private_key:
        raise KeyProtectionError(
            "Chave privada inválida."
        )

    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)

    key = derive_key(
        password,
        salt,
    )

    cipher = AESGCM(key)

    ciphertext = cipher.encrypt(
        nonce,
        private_key,
        None,
    )

    return {
        "version": VERSION,
        "algorithm": "AES-256-GCM",
        "kdf": "scrypt",
        "kdf_parameters": {
            "n": 2**14,
            "r": 8,
            "p": 1,
        },
        "salt": _b64_encode(salt),
        "nonce": _b64_encode(nonce),
        "ciphertext": _b64_encode(ciphertext),
        "key_fingerprint": hashlib.sha256(
            private_key
        ).hexdigest(),
    }


def decrypt_private_key(
    encrypted: dict,
    password: str,
) -> bytes:

    if not isinstance(encrypted, dict):
        raise KeyProtectionError(
            "Registro de chave inválido."
        )

    if encrypted.get("algorithm") != "AES-256-GCM":
        raise KeyProtectionError(
            "Algoritmo de proteção incompatível."
        )

    if encrypted.get("kdf") != "scrypt":
        raise KeyProtectionError(
            "KDF incompatível."
        )

    try:
        salt = _b64_decode(encrypted["salt"])
        nonce = _b64_decode(encrypted["nonce"])
        ciphertext = _b64_decode(
            encrypted["ciphertext"]
        )
    except Exception as exc:
        raise KeyProtectionError(
            "Dados criptográficos inválidos."
        ) from exc

    key = derive_key(
        password,
        salt,
    )

    cipher = AESGCM(key)

    try:
        private_key = cipher.decrypt(
            nonce,
            ciphertext,
            None,
        )
    except Exception as exc:
        raise KeyProtectionError(
            "Senha incorreta ou chave corrompida."
        ) from exc

    expected = encrypted.get(
        "key_fingerprint"
    )

    actual = hashlib.sha256(
        private_key
    ).hexdigest()

    if expected != actual:
        raise KeyProtectionError(
            "Fingerprint da chave não confere."
        )

    return private_key


def protect_identity(
    password: str,
) -> dict:

    if not CONFIG_PATH.exists():
        raise KeyProtectionError(
            f"Identidade não encontrada: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        identity = json.load(handle)

    private_key_b64 = identity.get(
        "private_key"
    )

    if not private_key_b64:
        raise KeyProtectionError(
            "Chave privada não encontrada."
        )

    try:
        private_key = _b64_decode(
            private_key_b64
        )
    except Exception as exc:
        raise KeyProtectionError(
            "Chave privada inválida."
        ) from exc

    encrypted = encrypt_private_key(
        private_key,
        password,
    )

    identity.pop(
        "private_key",
        None,
    )

    identity["private_key_protected"] = encrypted
    identity["key_protection"] = "AES-256-GCM"

    temp_path = CONFIG_PATH.with_suffix(
        ".json.tmp"
    )

    with temp_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            identity,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")

    os.replace(
        temp_path,
        CONFIG_PATH,
    )

    return identity


def load_protected_private_key(
    password: str,
) -> bytes:

    if not CONFIG_PATH.exists():
        raise KeyProtectionError(
            "Identidade não encontrada."
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:
        identity = json.load(handle)

    encrypted = identity.get(
        "private_key_protected"
    )

    if not encrypted:
        raise KeyProtectionError(
            "Chave privada não está protegida."
        )

    return decrypt_private_key(
        encrypted,
        password,
    )
