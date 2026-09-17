import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node import object_signature, crypto_identity


OBJECT_ID = "object-signature-test"
NAMESPACE = "security_test"
CONTENT_HASH = (
    "a" * 64
)
SIZE = 4096


def main():
    from getpass import getpass

    password = getpass("Senha da identidade: ")

    crypto_identity.unlock(password)

    print("\nCLISER DATA NODE — OBJECT SIGNATURE TEST")
    print("=" * 50)

    payload = object_signature.canonical_payload(
        object_id=OBJECT_ID,
        namespace=NAMESPACE,
        content_hash=CONTENT_HASH,
        size=SIZE,
    )

    assert isinstance(payload, bytes)

    print("CANONICAL PAYLOAD: OK")

    digest = object_signature.object_digest(
        object_id=OBJECT_ID,
        namespace=NAMESPACE,
        content_hash=CONTENT_HASH,
        size=SIZE,
    )

    assert len(digest) == 64

    print("PAYLOAD DIGEST: OK")

    signature = object_signature.sign_object(
        object_id=OBJECT_ID,
        namespace=NAMESPACE,
        content_hash=CONTENT_HASH,
        size=SIZE,
    )

    assert signature["algorithm"] == "Ed25519"
    assert signature["signature_version"] == 1
    assert signature["signer_identity"]
    assert signature["signer_fingerprint"]
    assert signature["payload_digest"]
    assert signature["signature"]

    print("OBJECT SIGNATURE: OK")
    print("SIGNER IDENTITY: OK")
    print("SIGNER FINGERPRINT: OK")

    valid = object_signature.verify_object(
        object_id=OBJECT_ID,
        namespace=NAMESPACE,
        content_hash=CONTENT_HASH,
        size=SIZE,
        signature_record=signature,
    )

    assert valid

    print("SIGNATURE VERIFICATION: OK")

    altered_namespace = "attacker_namespace"

    invalid_namespace = object_signature.verify_object(
        object_id=OBJECT_ID,
        namespace=altered_namespace,
        content_hash=CONTENT_HASH,
        size=SIZE,
        signature_record=signature,
    )

    assert not invalid_namespace

    print("ALTERED NAMESPACE REJECTED: OK")

    invalid_size = object_signature.verify_object(
        object_id=OBJECT_ID,
        namespace=NAMESPACE,
        content_hash=CONTENT_HASH,
        size=SIZE + 1,
        signature_record=signature,
    )

    assert not invalid_size

    print("ALTERED SIZE REJECTED: OK")

    altered_hash = "b" * 64

    invalid_hash = object_signature.verify_object(
        object_id=OBJECT_ID,
        namespace=NAMESPACE,
        content_hash=altered_hash,
        size=SIZE,
        signature_record=signature,
    )

    assert not invalid_hash

    print("ALTERED CONTENT HASH REJECTED: OK")

    reordered_payload = object_signature.canonical_payload(
        size=SIZE,
        content_hash=CONTENT_HASH,
        namespace=NAMESPACE,
        object_id=OBJECT_ID,
    )

    assert reordered_payload == payload

    print("CANONICALIZATION DETERMINISTIC: OK")

    crypto_identity.lock()

    print("PRIVATE KEY LOCKED: OK")

    print("\n" + "=" * 50)
    print("OBJECT SIGNATURE: PASS")
    print("FASE 13.6.4 — ASSINATURA COM CHAVE PROTEGIDA VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
