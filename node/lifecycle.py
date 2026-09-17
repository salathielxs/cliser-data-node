from pathlib import Path

from node.registry import (
    connect,
    rebuild_block_ref_counts,
    delete_manifest,
    delete_unreferenced_blocks,
    mark_block_deleted,
    remove_block_record,
)
from node.object_manager import (
    get_object_data,
    verify_object,
    delete_object_data,
    garbage_collect,
    reconcile_storage,
)


BASE_DIR = Path(__file__).resolve().parent.parent
BLOCKS_DIR = BASE_DIR / "storage" / "blocks"


def rebuild_references():
    rebuild_block_ref_counts()

    return {
        "status": "OK",
        "operation": "REFERENCE_REBUILD",
    }


def find_orphan_blocks():
    rows = delete_unreferenced_blocks()

    return [
        {
            "block_id": block_id,
            "storage_path": storage_path,
        }
        for block_id, storage_path in rows
    ]


def garbage_collect_blocks():
    removed = 0
    cleaned = 0

    candidates = find_orphan_blocks()

    for block in candidates:
        block_id = block["block_id"]
        storage_path = Path(block["storage_path"])

        if not mark_block_deleted(block_id):
            continue

        if storage_path.exists():
            storage_path.unlink()
            removed += 1

        if remove_block_record(block_id):
            cleaned += 1

    return {
        "candidates": len(candidates),
        "physical_removed": removed,
        "registry_cleaned": cleaned,
    }


def verify_storage_consistency():
    conn = connect()

    blocks = conn.execute("""
        SELECT
            block_id,
            ref_count,
            status,
            storage_path
        FROM blocks
    """).fetchall()

    manifest_refs = conn.execute("""
        SELECT
            block_id,
            COUNT(*)
        FROM manifest_blocks
        GROUP BY block_id
    """).fetchall()

    conn.close()

    calculated = {
        block_id: count
        for block_id, count in manifest_refs
    }

    registered_ids = {
        block_id
        for block_id, _, _, _ in blocks
    }

    physical_files = {
        path.name: path
        for path in BLOCKS_DIR.iterdir()
        if path.is_file()
    } if BLOCKS_DIR.exists() else {}

    physical_ids = set(physical_files)

    errors = []
    warnings = []

    # --------------------------------------------------------
    # 1. Registry -> Physical
    # --------------------------------------------------------

    for block_id, ref_count, status, storage_path in blocks:
        expected = calculated.get(block_id, 0)
        physical_exists = Path(storage_path).exists()

        if ref_count != expected:
            errors.append({
                "type": "REF_COUNT_MISMATCH",
                "block_id": block_id,
                "stored": ref_count,
                "calculated": expected,
            })

        if status == "ACTIVE" and not physical_exists:
            errors.append({
                "type": "MISSING_PHYSICAL_BLOCK",
                "block_id": block_id,
            })

    # --------------------------------------------------------
    # 2. Physical -> Registry
    # --------------------------------------------------------

    physical_orphans = sorted(
        physical_ids - registered_ids
    )

    for block_id in physical_orphans:
        path = physical_files[block_id]

        warnings.append({
            "type": "PHYSICAL_ORPHAN",
            "block_id": block_id,
            "storage_path": str(path),
            "size": path.stat().st_size,
        })

    # --------------------------------------------------------
    # 3. Determine status
    # --------------------------------------------------------

    if errors:
        status = "ERROR"
    elif warnings:
        status = "WARNING"
    else:
        status = "OK"

    return {
        "status": status,
        "registry_blocks": len(blocks),
        "manifest_references": sum(calculated.values()),
        "physical_blocks": len(physical_files),
        "missing_blocks": sum(
            1
            for block_id, _, block_status, storage_path in blocks
            if block_status == "ACTIVE"
            and not Path(storage_path).exists()
        ),
        "physical_orphans": len(physical_orphans),
        "refcount_mismatches": sum(
            1
            for block_id, ref_count, _, _ in blocks
            if ref_count != calculated.get(block_id, 0)
        ),
        "errors": errors,
        "warnings": warnings,
    }


def lifecycle_status():
    consistency = verify_storage_consistency()

    return {
        "status": consistency["status"],
        "consistency": consistency,
    }
