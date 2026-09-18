from __future__ import annotations

import base64
import hashlib
import json
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from node import key_protection


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
IDENTITY_FILE = CONFIG_DIR / "crypto_identity.json"


# Chave privada desbloqueada somente em memória.
_UNLOCKED_PRIVATE_KEY: Ed25519PrivateKey | None = None


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.b64decode(
        value.encode("ascii")
    )


def _public_key_bytes(
    public_key: Ed25519PublicKey,
) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _private_key_bytes(
    private_key: Ed25519PrivateKey,
) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def fingerprint(
    public_key: Ed25519PublicKey,
) -> str:
    return hashlib.sha256(
        _public_key_bytes(public_key)
    ).hexdigest()


def generate_identity(
    password: str,
) -> dict:
    """
    Gera uma nova identidade e retorna somente
    a forma protegida da chave privada.
    """

    if not isinstance(password, str) or not password:
        raise ValueError("Senha de proteção obrigatória.")

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    public_bytes = _public_key_bytes(public_key)
    private_bytes = _private_key_bytes(private_key)

    protected = key_protection.encrypt_private_key(
        private_bytes,
        password,
    )

    return {
        "identity_version": 1,
        "identity_id": secrets.token_hex(16),
        "algorithm": "Ed25519",
        "public_key": _b64(public_bytes),
        "fingerprint": fingerprint(public_key),
        "key_protection": "AES-256-GCM",
        "private_key_protected": protected,
    }


def save_identity(identity: dict) -> dict:
    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    required = {
        "identity_version",
        "identity_id",
        "algorithm",
        "public_key",
        "fingerprint",
    }

    missing = required - set(identity)

    if missing:
        raise ValueError(
            f"Campos ausentes: {sorted(missing)}"
        )

    if "private_key" in identity:
        raise ValueError(
            "Chave privada em texto aberto não é permitida."
        )

    if "private_key_protected" not in identity:
        raise ValueError(
            "Chave privada protegida não encontrada."
        )

    IDENTITY_FILE.write_text(
        json.dumps(
            identity,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        IDENTITY_FILE.chmod(0o600)
    except OSError:
        pass

    return identity


def load_identity() -> dict:
    if not IDENTITY_FILE.exists():
        raise FileNotFoundError(
            f"Identidade não encontrada: {IDENTITY_FILE}"
        )

    identity = json.loads(
        IDENTITY_FILE.read_text(
            encoding="utf-8"
        )
    )

    if identity.get("algorithm") != "Ed25519":
        raise ValueError(
            "Algoritmo de identidade inválido."
        )

    if "private_key" in identity:
        raise ValueError(
            "Identidade contém chave privada em texto aberto."
        )

    if "private_key_protected" not in identity:
        raise ValueError(
            "Identidade não possui chave privada protegida."
        )

    return identity


def unlock(password: str) -> Ed25519PrivateKey:
    """
    Desbloqueia a chave privada protegida e mantém
    a chave somente na memória do processo.
    """

    global _UNLOCKED_PRIVATE_KEY

    identity = load_identity()

    private_bytes = (
        key_protection.load_protected_private_key(
            password
        )
    )

    private_key = (
        Ed25519PrivateKey.from_private_bytes(
            private_bytes
        )
    )

    public_key = private_key.public_key()

    expected_fingerprint = identity["fingerprint"]
    actual_fingerprint = fingerprint(public_key)

    if actual_fingerprint != expected_fingerprint:
        raise ValueError(
            "Fingerprint da identidade não confere."
        )

    _UNLOCKED_PRIVATE_KEY = private_key

    return private_key


def lock() -> None:
    """
    Remove a referência da chave privada desbloqueada
    do módulo.
    """

    global _UNLOCKED_PRIVATE_KEY
    _UNLOCKED_PRIVATE_KEY = None


def is_unlocked() -> bool:
    return _UNLOCKED_PRIVATE_KEY is not None


def load_private_key(
    password: str | None = None,
) -> Ed25519PrivateKey:

    if password is not None:
        return unlock(password)

    if _UNLOCKED_PRIVATE_KEY is None:
        raise key_protection.KeyProtectionError(
            "Chave privada bloqueada. "
            "Execute crypto_identity.unlock(password)."
        )

    return _UNLOCKED_PRIVATE_KEY


def load_public_key() -> Ed25519PublicKey:
    identity = load_identity()

    return Ed25519PublicKey.from_public_bytes(
        _unb64(identity["public_key"])
    )


def sign(data: bytes) -> bytes:
    if not isinstance(data, bytes):
        raise TypeError(
            "data deve ser bytes."
        )

    return load_private_key().sign(data)


def verify(
    data: bytes,
    signature: bytes,
) -> bool:

    if not isinstance(data, bytes):
        raise TypeError(
            "data deve ser bytes."
        )

    if not isinstance(signature, bytes):
        raise TypeError(
            "signature deve ser bytes."
        )

    try:
        load_public_key().verify(
            signature,
            data,
        )
        return True
    except Exception:
        return False



def verify_with_public_key(
    data: bytes,
    signature: bytes,
    public_key: Ed25519PublicKey,
) -> bool:
    """
    Verifica uma assinatura Ed25519 usando uma chave pública fornecida.

    Não utiliza a identidade pública local e não requer
    desbloqueio da chave privada.
    """

    if not isinstance(data, bytes):
        raise TypeError("data deve ser bytes.")

    if not isinstance(signature, bytes):
        raise TypeError("signature deve ser bytes.")

    if not isinstance(public_key, Ed25519PublicKey):
        raise TypeError(
            "public_key deve ser Ed25519PublicKey."
        )

    try:
        public_key.verify(
            signature,
            data,
        )
        return True
    except Exception:
        return False


def initialize(
    password: str | None = None,
) -> dict:

    if IDENTITY_FILE.exists():
        return load_identity()

    if not password:
        raise ValueError(
            "Senha obrigatória para criar identidade."
        )

    identity = generate_identity(
        password
    )

    save_identity(identity)

    return identity
