from pathlib import Path
import sqlite3

from node.object_manager import put_object, delete_object_data, garbage_collect
from node.registry import (
    connect,
    get_manifest,
    get_object,
    create_namespace,
)
from node.quota import register_quota


BASE_DIR = Path(__file__).resolve().parent.parent
BLOCKS_DIR = BASE_DIR / "storage" / "blocks"
OBJECTS_DIR = BASE_DIR / "storage" / "objects"

NS = "gc_consistency"


def cleanup_namespace():
    conn = connect()

    rows = conn.execute("""
        SELECT object_id
        FROM objects
        WHERE namespace = ?
    """, (NS,)).fetchall()

    conn.close()

    for (object_id,) in rows:
        delete_object_data(object_id)

    garbage_collect()


def registry_snapshot():
    conn = connect()

    objects = conn.execute("""
        SELECT object_id, namespace, status, storage_path
        FROM objects
        WHERE namespace = ?
    """, (NS,)).fetchall()

    manifests = conn.execute("""
        SELECT object_id, namespace, status
        FROM manifests
        WHERE namespace = ?
    """, (NS,)).fetchall()

    manifest_blocks = conn.execute("""
        SELECT mb.object_id, mb.block_id, mb.block_index
        FROM manifest_blocks mb
        JOIN manifests m
          ON m.object_id = mb.object_id
        WHERE m.namespace = ?
    """, (NS,)).fetchall()

    conn.close()

    return {
        "objects": objects,
        "manifests": manifests,
        "manifest_blocks": manifest_blocks,
    }


def test_post_gc_consistency():
    print("=" * 60)
    print("POST-GC / REGISTRY CONSISTENCY TEST")
    print("=" * 60)

    cleanup_namespace()

    # Criar namespace de teste.
    conn = connect()
    existing = conn.execute("""
        SELECT namespace
        FROM namespaces
        WHERE namespace = ?
    """, (NS,)).fetchone()
    conn.close()

    if existing is None:
        create_namespace(NS)

    # Quota 0 = ilimitada.
    register_quota(NS, 0)

    data = b"CLISER-GC-CONSISTENCY-" * 500

    result = put_object(
        data,
        namespace=NS,
    )

    object_id = result["object_id"]

    obj = get_object(object_id)
    manifest = get_manifest(object_id)

    assert obj is not None
    assert obj["status"] == "ACTIVE"

    assert manifest is not None
    assert manifest["status"] == "ACTIVE"

    print("OBJECT + MANIFEST: OK")

    block_ids = [
        block["block_id"]
        for block in manifest["blocks"]
    ]

    assert block_ids
    print(f"BLOCKS CREATED: {len(block_ids)}")

    # O objeto precisa reconstruir antes da exclusão.
    from node.object_manager import get_object_data

    assert get_object_data(object_id) == data
    print("RECONSTRUCTION: OK")

    # Excluir objeto.
    deleted, status = delete_object_data(object_id)

    assert deleted
    print(f"DELETE: {status}")

    # O registro lógico deve estar deletado.
    obj_after_delete = get_object(object_id)

    assert obj_after_delete is not None
    assert obj_after_delete["status"] == "DELETED"

    print("OBJECT SOFT DELETE: OK")

    # Manifest deve ter sido removido/desativado.
    manifest_after_delete = get_manifest(object_id)

    assert manifest_after_delete is not None
    assert manifest_after_delete["status"] == "DELETED"
    print("MANIFEST SOFT DELETE: OK")

    # Executar GC.
    gc = garbage_collect()

    print(f"GC RESULT: {gc}")

    assert not gc["errors"]

    # Objeto lógico ainda pode existir como DELETED,
    # mas não deve possuir arquivo físico.
    obj_final = get_object(object_id)

    assert obj_final is not None
    assert obj_final["status"] == "DELETED"

    if obj_final["storage_path"]:
        assert not Path(obj_final["storage_path"]).exists()

    print("OBJECT PHYSICAL STORAGE: OK")

    # Nenhum manifest deve existir.
    conn = connect()

    manifest_count = conn.execute("""
        SELECT COUNT(*)
        FROM manifests
        WHERE object_id = ?
    """, (object_id,)).fetchone()[0]

    manifest_block_count = conn.execute("""
        SELECT COUNT(*)
        FROM manifest_blocks
        WHERE object_id = ?
    """, (object_id,)).fetchone()[0]

    # Nenhum bloco pode continuar referenciado.
    referenced_blocks = conn.execute("""
        SELECT COUNT(*)
        FROM manifest_blocks mb
        JOIN manifests m
          ON m.object_id = mb.object_id
        WHERE m.namespace = ?
    """, (NS,)).fetchone()[0]

    conn.close()

    assert manifest_count == 1
    assert manifest_block_count == 0
    assert referenced_blocks == 0

    conn = connect()

    manifest_status = conn.execute("""
        SELECT status
        FROM manifests
        WHERE object_id = ?
    """, (object_id,)).fetchone()

    conn.close()

    assert manifest_status is not None
    assert manifest_status[0] == "DELETED"

    print("DELETED MANIFEST RETAINED: OK")
    print("NO ORPHAN MANIFEST_BLOCKS: OK")
    print("NO ACTIVE BLOCK REFERENCES: OK")

    # Nenhum bloco criado pelo objeto deve permanecer fisicamente.
    remaining_files = []

    for block_id in block_ids:
        matches = list(BLOCKS_DIR.rglob(block_id))

        if matches:
            remaining_files.extend(matches)

    assert not remaining_files

    print("NO ORPHAN PHYSICAL BLOCKS: OK")

    # Snapshot final do namespace.
    snapshot = registry_snapshot()

    assert snapshot["manifests"]

    deleted_manifests = [
        m for m in snapshot["manifests"]
        if m[0] == object_id
        and m[2] == "DELETED"
    ]

    assert len(deleted_manifests) == 1
    print("DELETED MANIFEST IN SNAPSHOT: OK")
    assert not snapshot["manifest_blocks"]

    print("FINAL REGISTRY CONSISTENCY: OK")

    # Limpeza final.
    cleanup_namespace()

    print("=" * 60)
    print("POST-GC CONSISTENCY: OK")
    print("=" * 60)


if __name__ == "__main__":
    test_post_gc_consistency()
