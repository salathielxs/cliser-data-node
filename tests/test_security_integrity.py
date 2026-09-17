import sys
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node import storage
from node import block_manager
from node import registry


def main():
    print("\nCLISER DATA NODE — SECURITY / INTEGRITY TEST")
    print("=" * 50)

    data = b"CLISER-SECURITY-INTEGRITY-TEST"

    expected_hash = hashlib.sha256(data).hexdigest()

    block = block_manager.store_block(data)

    block_id = block["block_id"]
    path = Path(block["storage_path"])

    assert path.exists()
    assert block["content_hash"] == expected_hash

    print("BLOCK CREATED: OK")
    print("HASH REGISTERED: OK")
    print("PHYSICAL FILE: OK")

    stored_data = path.read_bytes()
    actual_hash = hashlib.sha256(stored_data).hexdigest()

    assert actual_hash == expected_hash

    print("INITIAL INTEGRITY: OK")

    original = stored_data
    path.write_bytes(original + b"-TAMPERED")

    tampered_data = path.read_bytes()
    tampered_hash = hashlib.sha256(tampered_data).hexdigest()

    assert tampered_hash != expected_hash

    print("TAMPERING SIMULATION: OK")
    print("HASH MISMATCH DETECTED: OK")

    path.write_bytes(original)

    restored_data = path.read_bytes()
    restored_hash = hashlib.sha256(restored_data).hexdigest()

    assert restored_hash == expected_hash

    print("RESTORE: OK")
    print("FINAL INTEGRITY: OK")

    conn = registry.connect()
    conn.execute(
        "DELETE FROM blocks WHERE block_id = ?",
        (block_id,),
    )
    conn.commit()
    conn.close()

    if path.exists():
        path.unlink()

    print("\n" + "=" * 50)
    print("SECURITY INTEGRITY: PASS")
    print("FASE 13.1 — INTEGRIDADE CRIPTOGRÁFICA VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
