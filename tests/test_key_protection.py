import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node.key_protection import (
    encrypt_private_key,
    decrypt_private_key,
    KeyProtectionError,
)


def main():
    print("\nCLISER DATA NODE — KEY PROTECTION TEST")
    print("=" * 50)

    private_key = bytes(range(32))
    password = "CLISER-TEST-PASSWORD-2026"

    encrypted = encrypt_private_key(
        private_key,
        password,
    )

    assert encrypted["algorithm"] == "AES-256-GCM"
    assert encrypted["kdf"] == "scrypt"

    print("AES-256-GCM: OK")
    print("SCRYPT: OK")
    print("KEY ENCRYPTION: OK")

    restored = decrypt_private_key(
        encrypted,
        password,
    )

    assert restored == private_key

    print("KEY DECRYPTION: OK")
    print("KEY RESTORATION: OK")

    rejected = False

    try:
        decrypt_private_key(
            encrypted,
            "WRONG-PASSWORD",
        )
    except KeyProtectionError:
        rejected = True

    assert rejected

    print("WRONG PASSWORD REJECTED: OK")

    altered = dict(encrypted)

    altered["ciphertext"] = (
        encrypted["ciphertext"][:-4]
        + "AAAA"
    )

    rejected = False

    try:
        decrypt_private_key(
            altered,
            password,
        )
    except KeyProtectionError:
        rejected = True

    assert rejected

    print("TAMPERING REJECTED: OK")

    print("\n" + "=" * 50)
    print("KEY PROTECTION: PASS")
    print("FASE 13.6.1 — PROTEÇÃO CRIPTOGRÁFICA VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
