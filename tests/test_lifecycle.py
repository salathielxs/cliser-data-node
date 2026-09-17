from pathlib import Path

from node.registry import (
    connect,
    get_block_ref_count,
    get_manifest,
)
from node.object_manager import (
    put_object,
    get_object_data,
    delete_object_data,
    garbage_collect,
)
from node.accounting import namespace_accounting
from node.quota import set_quota


NAMESPACE_A = "lifecycle_a"
NAMESPACE_B = "lifecycle_b"


def cleanup_namespaces():
    conn = connect()

    conn.execute("""
        DELETE FROM manifest_blocks
        WHERE object_id IN (
            SELECT object_id
            FROM manifests
            WHERE namespace IN (?, ?)
        )
    """, (NAMESPACE_A, NAMESPACE_B))

    conn.execute("""
        DELETE FROM manifests
        WHERE namespace IN (?, ?)
    """, (NAMESPACE_A, NAMESPACE_B))

    conn.execute("""
        DELETE FROM objects
        WHERE namespace IN (?, ?)
    """, (NAMESPACE_A, NAMESPACE_B))

    conn.execute("""
        DELETE FROM quotas
        WHERE namespace IN (?, ?)
    """, (NAMESPACE_A, NAMESPACE_B))

    conn.execute("""
        DELETE FROM namespaces
        WHERE namespace IN (?, ?)
    """, (NAMESPACE_A, NAMESPACE_B))

    conn.commit()
    conn.close()


def create_namespaces():
    conn = connect()

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    for namespace in (NAMESPACE_A, NAMESPACE_B):
        conn.execute("""
            INSERT OR IGNORE INTO namespaces
            (
                namespace,
                status,
                quota_bytes,
                created_at,
                updated_at
            )
            VALUES (?, 'ACTIVE', 0, ?, ?)
        """, (namespace, now, now))

    conn.commit()
    conn.close()

    set_quota(NAMESPACE_A, 0)
    set_quota(NAMESPACE_B, 0)


def test_shared_block_lifecycle():

    cleanup_namespaces()
    create_namespaces()

    data = b"CLISER-LIFECYCLE-SHARED-" * 100

    # ---------------------------------------------------------
    # CREATE A
    # ---------------------------------------------------------

    result_a = put_object(
        data,
        namespace=NAMESPACE_A,
    )

    object_a = result_a["object_id"]

    # ---------------------------------------------------------
    # CREATE B
    # ---------------------------------------------------------

    result_b = put_object(
        data,
        namespace=NAMESPACE_B,
    )

    object_b = result_b["object_id"]

    assert object_a != object_b
    assert result_a["content_hash"] == result_b["content_hash"]

    manifest_a = get_manifest(object_a)
    manifest_b = get_manifest(object_b)

    assert manifest_a is not None
    assert manifest_b is not None

    block_id = manifest_a["blocks"][0]["block_id"]

    assert manifest_b["blocks"][0]["block_id"] == block_id

    ref_count = get_block_ref_count(block_id)

    assert ref_count == 2

    print("CREATE SHARED BLOCK: OK")
    print("Initial ref_count:", ref_count)

    # ---------------------------------------------------------
    # DELETE A
    # ---------------------------------------------------------

    deleted, status = delete_object_data(object_a)

    assert deleted
    assert status == "DELETED_BLOCKS"

    ref_count = get_block_ref_count(block_id)

    assert ref_count == 1

    print("DELETE A: OK")
    print("ref_count after A:", ref_count)

    # ---------------------------------------------------------
    # B MUST REMAIN READABLE
    # ---------------------------------------------------------

    restored_b = get_object_data(object_b)

    assert restored_b == data

    print("OBJECT B PRESERVED: OK")

    # ---------------------------------------------------------
    # GC MUST NOT REMOVE SHARED BLOCK
    # ---------------------------------------------------------

    gc_result = garbage_collect()

    block_path = Path(
        result_b.get("storage_path")
        or f"storage/blocks/{block_id}"
    )

    assert block_path.exists()

    ref_count = get_block_ref_count(block_id)

    assert ref_count == 1

    print("GC PRESERVES SHARED BLOCK: OK")

    # ---------------------------------------------------------
    # DELETE B
    # ---------------------------------------------------------

    deleted, status = delete_object_data(object_b)

    assert deleted
    assert status == "DELETED_BLOCKS"

    # O registro físico ainda pode existir neste momento,
    # mas não deve possuir referências.
    ref_count = get_block_ref_count(block_id)

    assert ref_count == 0

    print("DELETE B: OK")
    print("ref_count after B:", ref_count)

    # ---------------------------------------------------------
    # GC FINAL
    # ---------------------------------------------------------

    gc_result = garbage_collect()

    print("GC RESULT:", gc_result)

    # O registro do bloco deve desaparecer.
    assert get_block_ref_count(block_id) is None

    block_path = Path("storage/blocks") / block_id

    assert not block_path.exists()

    print("ORPHAN BLOCK REMOVED: OK")
    print("PHYSICAL BLOCK REMOVED: OK")

    cleanup_namespaces()


if __name__ == "__main__":
    print("=" * 60)
    print("LIFECYCLE / SHARED BLOCK GC TEST")
    print("=" * 60)

    test_shared_block_lifecycle()

    print("=" * 60)
    print("LIFECYCLE / GC: OK")
    print("=" * 60)
