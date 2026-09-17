import sys
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node import registry
from node import object_manager
from node import manifest
from node.namespace_manager import namespace_exists, create_namespace


TEST_NS = "security_integrity_test"

DATA = (
    b"CLISER DATA NODE - END TO END INTEGRITY - "
    b"0123456789ABCDEF"
)


def cleanup():
    conn = registry.connect()

    rows = conn.execute(
        """
        SELECT mb.block_id, b.storage_path
        FROM manifest_blocks mb
        JOIN blocks b
            ON b.block_id = mb.block_id
        WHERE mb.object_id IN (
            SELECT object_id
            FROM manifests
            WHERE namespace = ?
        )
        """,
        (TEST_NS,),
    ).fetchall()

    blocks = [
        (row[0], Path(row[1]))
        for row in rows
    ]

    conn.execute(
        """
        DELETE FROM manifest_blocks
        WHERE object_id IN (
            SELECT object_id
            FROM manifests
            WHERE namespace = ?
        )
        """,
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM manifests WHERE namespace = ?",
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM objects WHERE namespace = ?",
        (TEST_NS,),
    )

    conn.commit()

    for block_id, storage_path in blocks:
        conn.execute(
            """
            DELETE FROM blocks
            WHERE block_id = ?
            """,
            (block_id,),
        )

    conn.commit()
    conn.close()

    for _, storage_path in blocks:
        if storage_path.exists():
            storage_path.unlink()


def main():
    print("\nCLISER DATA NODE — OBJECT INTEGRITY TEST")
    print("=" * 50)

    cleanup()

    if not namespace_exists(TEST_NS):
        create_namespace(TEST_NS, quota_bytes=0)

    expected_hash = hashlib.sha256(DATA).hexdigest()

    print("[1] CREATING OBJECT")

    result = object_manager.put_object(
        DATA,
        namespace=TEST_NS,
        quota_mode="LOGICAL",
    )

    object_id = result["object_id"]

    assert object_id
    print("OBJECT CREATED: OK")

    obj = registry.get_object(object_id)

    assert obj is not None
    assert obj["content_hash"] == expected_hash
    assert obj["size"] == len(DATA)

    print("OBJECT HASH: OK")
    print("OBJECT SIZE: OK")

    print("\n[2] RECONSTRUCTING OBJECT")

    reconstructed = manifest.reconstruct_object(object_id)

    assert reconstructed == DATA

    reconstructed_hash = hashlib.sha256(
        reconstructed
    ).hexdigest()

    assert reconstructed_hash == expected_hash

    print("RECONSTRUCTION: OK")
    print("END-TO-END HASH: OK")

    print("\n[3] LOCATING PHYSICAL BLOCK")

    conn = registry.connect()

    rows = conn.execute(
        """
        SELECT mb.block_id, b.storage_path
        FROM manifest_blocks mb
        JOIN blocks b
            ON b.block_id = mb.block_id
        WHERE mb.object_id = ?
        ORDER BY mb.block_index
        """,
        (object_id,),
    ).fetchall()

    conn.close()

    assert rows

    block_id, storage_path = rows[0]

    block_path = Path(storage_path)

    assert block_path.exists()

    original_block = block_path.read_bytes()

    print("BLOCK LOCATED: OK")
    print("PHYSICAL BLOCK: OK")

    print("\n[4] CORRUPTION SIMULATION")

    block_path.write_bytes(
        original_block + b"CORRUPTION"
    )

    corrupted = block_path.read_bytes()

    corrupted_hash = hashlib.sha256(
        corrupted
    ).hexdigest()

    assert corrupted_hash != block_id

    print("BLOCK CORRUPTED: OK")
    print("CORRUPTED HASH DETECTED: OK")

    print("\n[5] OBJECT RECONSTRUCTION AFTER CORRUPTION")

    corruption_detected = False

    try:
        manifest.reconstruct_object(object_id)
    except Exception:
        corruption_detected = True

    assert corruption_detected

    print("OBJECT CORRUPTION DETECTED: OK")

    print("\n[6] RESTORING BLOCK")

    block_path.write_bytes(original_block)

    restored = block_path.read_bytes()

    restored_hash = hashlib.sha256(
        restored
    ).hexdigest()

    assert restored_hash == block_id

    print("BLOCK RESTORED: OK")
    print("BLOCK HASH RESTORED: OK")

    print("\n[7] FINAL OBJECT VALIDATION")

    final_data = manifest.reconstruct_object(object_id)

    assert final_data == DATA

    final_hash = hashlib.sha256(final_data).hexdigest()

    assert final_hash == expected_hash

    print("FINAL RECONSTRUCTION: OK")
    print("FINAL OBJECT HASH: OK")
    print("END-TO-END INTEGRITY: OK")

    cleanup()

    print("\n" + "=" * 50)
    print("OBJECT INTEGRITY: PASS")
    print("FASE 13.2 — INTEGRIDADE PONTA A PONTA VALIDADA")
    print("=" * 50)


if __name__ == "__main__":
    main()
