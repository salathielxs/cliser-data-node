import os
import sqlite3
import hashlib
from pathlib import Path

ROOT = Path.cwd()
DB = ROOT / "data" / "registry.db"
BLOCK_DIR = ROOT / "storage" / "blocks"
OBJECT_DIR = ROOT / "storage" / "objects"

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

conn = sqlite3.connect(DB)
conn.execute("PRAGMA foreign_keys = ON")

print("=" * 72)
print("CLISER DATA NODE — 14.25.6 STORAGE FINAL AUDIT")
print("=" * 72)

# ------------------------------------------------------------
# 1. BLOCK REGISTRY
# ------------------------------------------------------------
blocks = conn.execute("""
    SELECT block_id, content_hash, size, storage_path, status, ref_count
    FROM blocks
    ORDER BY block_id
""").fetchall()

registry_block_ids = {r[0] for r in blocks}

physical_blocks = {
    p.name: p
    for p in BLOCK_DIR.iterdir()
    if p.is_file()
}

print("\n[1] BLOCK REGISTRY")
print(f"Registry blocks       : {len(blocks)}")
print(f"Physical block files  : {len(physical_blocks)}")

# ------------------------------------------------------------
# 2. PHYSICAL BLOCKS WITHOUT REGISTRY
# ------------------------------------------------------------
physical_without_registry = sorted(
    set(physical_blocks) - registry_block_ids
)

print("\n[2] PHYSICAL BLOCKS WITHOUT REGISTRY")
print(f"Count: {len(physical_without_registry)}")

for x in physical_without_registry:
    print(f"  {x}")

# ------------------------------------------------------------
# 3. REGISTRY BLOCKS WITHOUT FILE
# ------------------------------------------------------------
registry_without_file = []

for block_id, content_hash, size, storage_path, status, ref_count in blocks:
    path = Path(storage_path) if storage_path else BLOCK_DIR / block_id

    if not path.exists():
        registry_without_file.append(
            (block_id, status, size, storage_path)
        )

print("\n[3] REGISTRY BLOCKS WITHOUT PHYSICAL FILE")
print(f"Count: {len(registry_without_file)}")

for row in registry_without_file:
    print(" ", row)

# ------------------------------------------------------------
# 4. ACTIVE BLOCK HASH/SIZE VALIDATION
# ------------------------------------------------------------
block_hash_errors = []
block_size_errors = []

for block_id, content_hash, size, storage_path, status, ref_count in blocks:
    if status != "ACTIVE":
        continue

    path = Path(storage_path) if storage_path else BLOCK_DIR / block_id

    if not path.exists():
        continue

    actual_size = path.stat().st_size
    actual_hash = sha256_file(path)

    if actual_size != size:
        block_size_errors.append(
            (block_id, size, actual_size)
        )

    if actual_hash != content_hash:
        block_hash_errors.append(
            (block_id, content_hash, actual_hash)
        )

print("\n[4] ACTIVE BLOCK SIZE VALIDATION")
print(f"Errors: {len(block_size_errors)}")

for row in block_size_errors:
    print(" ", row)

print("\n[5] ACTIVE BLOCK SHA-256 VALIDATION")
print(f"Errors: {len(block_hash_errors)}")

for row in block_hash_errors:
    print(" ", row)

# ------------------------------------------------------------
# 6. BLOCK STORAGE PATH VALIDATION
# ------------------------------------------------------------
path_errors = []

block_root = BLOCK_DIR.resolve()

for block_id, content_hash, size, storage_path, status, ref_count in blocks:
    if not storage_path:
        continue

    try:
        resolved = Path(storage_path).resolve()

        if block_root not in resolved.parents and resolved != block_root:
            path_errors.append(
                (block_id, storage_path)
            )
    except Exception:
        path_errors.append(
            (block_id, storage_path)
        )

print("\n[6] BLOCK STORAGE PATH VALIDATION")
print(f"Errors: {len(path_errors)}")

for row in path_errors:
    print(" ", row)

# ------------------------------------------------------------
# 7. OBJECT REGISTRY
# ------------------------------------------------------------
objects = conn.execute("""
    SELECT object_id, content_hash, size, storage_path,
           namespace, status
    FROM objects
    ORDER BY object_id
""").fetchall()

physical_objects = {
    p.name: p
    for p in OBJECT_DIR.iterdir()
    if p.is_file()
}

print("\n[7] OBJECT STORAGE")
print(f"Registry objects      : {len(objects)}")
print(f"Physical object files : {len(physical_objects)}")

# ------------------------------------------------------------
# 8. ACTIVE OBJECTS THAT REQUIRE PHYSICAL FILE
# ------------------------------------------------------------
active_missing_files = []
active_hash_errors = []
active_size_errors = []

for object_id, content_hash, size, storage_path, namespace, status in objects:

    if status != "ACTIVE":
        continue

    # storage_path NULL = logical/non-materialized object
    if not storage_path:
        continue

    path = Path(storage_path)

    if not path.exists():
        active_missing_files.append(
            (object_id, storage_path, namespace)
        )
        continue

    actual_size = path.stat().st_size
    actual_hash = sha256_file(path)

    if actual_size != size:
        active_size_errors.append(
            (object_id, size, actual_size)
        )

    if actual_hash != content_hash:
        active_hash_errors.append(
            (object_id, content_hash, actual_hash)
        )

print("\n[8] ACTIVE OBJECTS — MISSING PHYSICAL FILE")
print(f"Count: {len(active_missing_files)}")

for row in active_missing_files:
    print(" ", row)

print("\n[9] ACTIVE OBJECTS — SIZE VALIDATION")
print(f"Errors: {len(active_size_errors)}")

for row in active_size_errors:
    print(" ", row)

print("\n[10] ACTIVE OBJECTS — SHA-256 VALIDATION")
print(f"Errors: {len(active_hash_errors)}")

for row in active_hash_errors:
    print(" ", row)

# ------------------------------------------------------------
# 11. PHYSICAL OBJECTS WITHOUT REGISTRY
# ------------------------------------------------------------
registry_object_ids = {r[0] for r in objects}

physical_objects_without_registry = []

for filename, path in physical_objects.items():
    if filename not in registry_object_ids:
        physical_objects_without_registry.append(filename)

print("\n[11] PHYSICAL OBJECTS WITHOUT REGISTRY")
print(f"Count: {len(physical_objects_without_registry)}")

for x in sorted(physical_objects_without_registry):
    print(f"  {x}")

# ------------------------------------------------------------
# 12. OBJECT CLASSIFICATION
# ------------------------------------------------------------
active_objects = sum(1 for r in objects if r[5] == "ACTIVE")
deleted_objects = sum(1 for r in objects if r[5] == "DELETED")
logical_objects = sum(
    1 for r in objects
    if r[5] == "ACTIVE" and not r[3]
)

print("\n[12] OBJECT CLASSIFICATION")
print(f"ACTIVE objects       : {active_objects}")
print(f"DELETED objects      : {deleted_objects}")
print(f"ACTIVE logical-only  : {logical_objects}")
print(f"Physical objects     : {len(physical_objects)}")

# ------------------------------------------------------------
# 13. ACTIVE MANIFESTS
# ------------------------------------------------------------
manifest_errors = []

active_manifests = conn.execute("""
    SELECT object_id, namespace, total_size,
           block_size, block_count, status
    FROM manifests
    WHERE status = 'ACTIVE'
""").fetchall()

for object_id, namespace, total_size, block_size, block_count, status in active_manifests:

    object_row = conn.execute("""
        SELECT status, size
        FROM objects
        WHERE object_id = ?
    """, (object_id,)).fetchone()

    if not object_row:
        manifest_errors.append(
            (object_id, "OBJECT_NOT_FOUND")
        )
        continue

    object_status, object_size = object_row

    if object_status != "ACTIVE":
        manifest_errors.append(
            (object_id, "OBJECT_NOT_ACTIVE", object_status)
        )

    blocks_data = conn.execute("""
        SELECT size
        FROM manifest_blocks
        WHERE object_id = ?
        ORDER BY block_index
    """, (object_id,)).fetchall()

    actual_count = len(blocks_data)
    actual_size = sum(x[0] for x in blocks_data)

    if actual_count != block_count:
        manifest_errors.append(
            (object_id, "BLOCK_COUNT", block_count, actual_count)
        )

    if actual_size != total_size:
        manifest_errors.append(
            (object_id, "TOTAL_SIZE", total_size, actual_size)
        )

    if object_size != total_size:
        manifest_errors.append(
            (object_id, "OBJECT_SIZE", object_size, total_size)
        )

print("\n[13] ACTIVE MANIFEST INTEGRITY")
print(f"Active manifests: {len(active_manifests)}")
print(f"Errors          : {len(manifest_errors)}")

for row in manifest_errors:
    print(" ", row)

# ------------------------------------------------------------
# 14. ZERO-REFERENCE BLOCKS
# ------------------------------------------------------------
zero_ref = conn.execute("""
    SELECT block_id, size, status
    FROM blocks
    WHERE ref_count = 0
""").fetchall()

print("\n[14] ZERO-REFERENCE BLOCKS")
print(f"Count: {len(zero_ref)}")

for row in zero_ref:
    print(" ", row)

# ------------------------------------------------------------
# 15. BLOCK REFERENCE CONSISTENCY
# ------------------------------------------------------------
ref_errors = conn.execute("""
    SELECT
        b.block_id,
        b.ref_count,
        COUNT(mb.block_id) AS actual_refs
    FROM blocks b
    LEFT JOIN manifest_blocks mb
        ON mb.block_id = b.block_id
    GROUP BY b.block_id
    HAVING b.ref_count != actual_refs
""").fetchall()

print("\n[15] BLOCK REFERENCE CONSISTENCY")
print(f"Errors: {len(ref_errors)}")

for row in ref_errors:
    print(" ", row)

# ------------------------------------------------------------
# 16. SQLITE INTEGRITY
# ------------------------------------------------------------
integrity = conn.execute("PRAGMA integrity_check;").fetchall()
foreign_keys = conn.execute("PRAGMA foreign_key_check;").fetchall()

print("\n[16] SQLITE INTEGRITY")
print(f"integrity_check : {integrity}")
print(f"foreign_key_check rows: {len(foreign_keys)}")

for row in foreign_keys:
    print(" ", row)

# ------------------------------------------------------------
# 17. STORAGE CAPACITY
# ------------------------------------------------------------
storage_bytes = 0

for base in [ROOT / "storage", ROOT / "data"]:
    if base.exists():
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    storage_bytes += p.stat().st_size
                except OSError:
                    pass

project_bytes = 0

for p in ROOT.rglob("*"):
    if p.is_file():
        try:
            project_bytes += p.stat().st_size
        except OSError:
            pass

def mb(n):
    return n / (1024 * 1024)

print("\n[17] CLISER DATA NODE STORAGE")
print(f"data + storage : {mb(storage_bytes):.2f} MB")
print(f"project total  : {mb(project_bytes):.2f} MB")

# ------------------------------------------------------------
# 18. DEVICE CONTEXT
# ------------------------------------------------------------
print("\n[18] DEVICE FILESYSTEM CONTEXT")
os.system("df -h .")

# ------------------------------------------------------------
# FINAL RESULT
# ------------------------------------------------------------
failures = (
    len(physical_without_registry)
    + len(registry_without_file)
    + len(block_size_errors)
    + len(block_hash_errors)
    + len(path_errors)
    + len(active_missing_files)
    + len(active_size_errors)
    + len(active_hash_errors)
    + len(physical_objects_without_registry)
    + len(manifest_errors)
    + len(zero_ref)
    + len(ref_errors)
    + len(foreign_keys)
)

print("\n" + "=" * 72)

if failures == 0:
    print("RESULTADO: PASS")
    print("Nenhuma inconsistência ativa encontrada.")
else:
    print("RESULTADO: REVIEW")
    print(f"Total de achados para revisão: {failures}")

print("=" * 72)

conn.close()
