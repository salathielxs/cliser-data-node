import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node import crypto_identity


def main():
    print("\nCLISER DATA NODE — CRYPTO IDENTITY TEST")
    print("=" * 50)

    identity = crypto_identity.initialize()

    assert identity["algorithm"] == "Ed25519"
    assert identity["identity_id"]
    assert identity["public_key"]
    assert identity["private_key"]
    assert identity["fingerprint"]

    print("IDENTITY CREATED/LOADED: OK")
    print("ALGORITHM: Ed25519")
    print("PUBLIC KEY: OK")
    print("FINGERPRINT: OK")

    data = b"CLISER DATA NODE - AUTHENTICATED OBJECT"

    signature = crypto_identity.sign(data)

    assert isinstance(signature, bytes)
    assert len(signature) == 64

    print("SIGNATURE GENERATED: OK")

    assert crypto_identity.verify(
        data,
        signature,
    )

    print("SIGNATURE VERIFIED: OK")

    altered_data = data + b"-ALTERED"

    assert not crypto_identity.verify(
        altered_data,
        signature,
    )

    print("ALTERED DATA REJECTED: OK")

    identity_again = crypto_identity.initialize()

    assert (
        identity_again["identity_id"]
        == identity["identity_id"]
    )

    assert (
        identity_again["fingerprint"]
        == identity["fingerprint"]
    )

    print("IDENTITY PERSISTENCE: OK")
    print("IDENTITY RELOAD: OK")

    print("\n" + "=" * 50)
    print("CRYPTO IDENTITY: PASS")
    print("FASE 13.3.2 — IDENTIDADE ED25519 VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
