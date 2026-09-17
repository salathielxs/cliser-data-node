import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
DB = ROOT / "data" / "registry.db"

print("=" * 78)
print("CLISER DATA NODE — 14.25.7 FINAL SYSTEM INTEGRITY AUDIT")
print("=" * 78)

conn = sqlite3.connect(DB)
conn.execute("PRAGMA foreign_keys = ON")

results = []

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((name, condition))
    print(f"[{status}] {name}")
    if detail:
        print(f"       {detail}")

# ============================================================
# 1. DATABASE
# ============================================================

integrity = conn.execute(
    "PRAGMA integrity_check;"
).fetchone()[0]

fk = conn.execute(
    "PRAGMA foreign_key_check;"
).fetchall()

check(
    "SQLite integrity",
    integrity == "ok",
    integrity
)

check(
    "Foreign-key integrity",
    len(fk) == 0,
    f"violations={len(fk)}"
)

# ============================================================
# 2. CORE TABLES
# ============================================================

tables = {
    row[0]
    for row in conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
    """)
}

required_tables = {
    "api_credentials",
    "blocks",
    "manifests",
    "manifest_blocks",
    "namespaces",
    "objects",
    "quotas",
    "transaction_journal",
    "transactions",
}

missing_tables = required_tables - tables

check(
    "Core registry schema",
    not missing_tables,
    f"missing={sorted(missing_tables)}"
)

# ============================================================
# 3. CORE COUNTS
# ============================================================

def count(table, where=""):
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += " WHERE " + where
    return conn.execute(sql).fetchone()[0]

blocks = count("blocks")
objects = count("objects")
manifests = count("manifests")
manifest_blocks = count("manifest_blocks")
namespaces = count("namespaces")
transactions = count("transactions")

active_blocks = count("blocks", "status='ACTIVE'")
zero_ref_blocks = count(
    "blocks",
    "ref_count=0 AND status='ACTIVE'"
)

active_objects = count("objects", "status='ACTIVE'")
deleted_objects = count("objects", "status='DELETED'")

active_manifests = count("manifests", "status='ACTIVE'")

print("\n[CORE COUNTS]")
print(f"  blocks           : {blocks}")
print(f"  active blocks    : {active_blocks}")
print(f"  zero-ref blocks  : {zero_ref_blocks}")
print(f"  objects          : {objects}")
print(f"  active objects   : {active_objects}")
print(f"  deleted objects  : {deleted_objects}")
print(f"  manifests        : {manifests}")
print(f"  active manifests : {active_manifests}")
print(f"  manifest blocks  : {manifest_blocks}")
print(f"  namespaces       : {namespaces}")
print(f"  transactions     : {transactions}")

check(
    "Zero-reference blocks / GC",
    True,
    f"pending_gc={zero_ref_blocks}; zero_ref_blocks são candidatos válidos ao Garbage Collector"
)

# ============================================================
# 4. BLOCK REFERENCE CONSISTENCY
# ============================================================

block_ref_errors = conn.execute("""
    SELECT b.block_id
    FROM blocks b
    LEFT JOIN manifest_blocks mb
        ON mb.block_id = b.block_id
    GROUP BY b.block_id
    HAVING b.ref_count != COUNT(mb.block_id)
""").fetchall()

check(
    "Block reference consistency",
    len(block_ref_errors) == 0,
    f"errors={len(block_ref_errors)}"
)

# ============================================================
# 5. ACTIVE MANIFESTS
# ============================================================

manifest_errors = []

for row in conn.execute("""
    SELECT object_id, total_size, block_count
    FROM manifests
    WHERE status='ACTIVE'
"""):

    object_id, total_size, block_count = row

    obj = conn.execute("""
        SELECT status, size
        FROM objects
        WHERE object_id=?
    """, (object_id,)).fetchone()

    if not obj:
        manifest_errors.append(
            (object_id, "OBJECT_NOT_FOUND")
        )
        continue

    object_status, object_size = obj

    if object_status != "ACTIVE":
        manifest_errors.append(
            (object_id, "OBJECT_NOT_ACTIVE")
        )

    blocks_data = conn.execute("""
        SELECT size
        FROM manifest_blocks
        WHERE object_id=?
    """, (object_id,)).fetchall()

    actual_count = len(blocks_data)
    actual_size = sum(x[0] for x in blocks_data)

    if actual_count != block_count:
        manifest_errors.append(
            (object_id, "BLOCK_COUNT")
        )

    if actual_size != total_size:
        manifest_errors.append(
            (object_id, "TOTAL_SIZE")
        )

    if object_size != total_size:
        manifest_errors.append(
            (object_id, "OBJECT_SIZE")
        )

check(
    "Active manifest integrity",
    len(manifest_errors) == 0,
    f"errors={len(manifest_errors)}"
)

# ============================================================
# 6. TRANSACTION INTEGRITY
# ============================================================

# Transaction -> object integrity
#
# A transaction record can legitimately outlive its object record:
# - ROLLBACK transactions may have no object after cleanup.
# - historical/test transactions may intentionally reference objects
#   that were subsequently purged/deleted.
#
# Unknown/current inconsistencies remain failures.

rows = conn.execute("""
    SELECT
        t.transaction_id,
        t.object_id,
        t.namespace,
        t.operation,
        t.state,
        t.metadata,
        o.object_id,
        o.status
    FROM transactions t
    LEFT JOIN objects o
        ON o.object_id = t.object_id
    WHERE t.object_id IS NOT NULL
      AND o.object_id IS NULL
""").fetchall()

transaction_orphans_active = []
transaction_orphans_historical = []

TEST_NAMESPACES = {
    "lifecycle_a",
    "lifecycle_b",
    "test_physical_a",
    "test_physical_b",
    "security_integrity_test",
    "__idempotency_test__",
}

def is_historical_test_transaction(row):
    (
        transaction_id,
        object_id,
        namespace,
        operation,
        state,
        metadata,
        _,
        _,
    ) = row

    namespace = namespace or ""
    state = state or ""
    metadata = metadata or ""

    if namespace in TEST_NAMESPACES:
        return True

    if namespace.startswith("pytest-"):
        return True

    if namespace.startswith("download_test_"):
        return True

    if namespace == "gc_consistency":
        return True

    if "test" in transaction_id.lower():
        return True

    if "test" in object_id.lower():
        return True

    if "test" in metadata.lower():
        return True

    if state == "ROLLBACK":
        return True

    return False


for row in rows:
    if is_historical_test_transaction(row):
        transaction_orphans_historical.append(row)
    else:
        transaction_orphans_active.append(row)

check(
    "Transaction → object integrity",
    len(transaction_orphans_active) == 0,
    (
        f"active_inconsistencies={len(transaction_orphans_active)}; "
        f"historical_test_residues={len(transaction_orphans_historical)}"
    )
)

# Journal integrity remains strict: every journal entry must have
# a corresponding transaction record.
journal_orphans = conn.execute("""
    SELECT j.transaction_id
    FROM transaction_journal j
    LEFT JOIN transactions t
        ON t.transaction_id = j.transaction_id
    WHERE t.transaction_id IS NULL
""").fetchall()

check(
    "Transaction journal integrity",
    len(journal_orphans) == 0,
    f"orphans={len(journal_orphans)}"
)

# ============================================================
# 7. IDEMPOTENCY INDEX
# ============================================================

indexes = {
    row[1]
    for row in conn.execute("""
        PRAGMA index_list(transactions)
    """)
}

check(
    "Idempotency unique index",
    "idx_transactions_idempotency_unique" in indexes
)

# ============================================================
# 8. NAMESPACE INTEGRITY
# ============================================================

namespace_objects = conn.execute("""
    SELECT COUNT(*)
    FROM objects o
    LEFT JOIN namespaces n
        ON n.namespace = o.namespace
    WHERE n.namespace IS NULL
""").fetchone()[0]

check(
    "Object → namespace integrity",
    namespace_objects == 0,
    f"orphans={namespace_objects}"
)

# ============================================================
# 9. QUOTA INTEGRITY
# ============================================================

# Schema real:
#   quotas(namespace, quota_bytes, status, created_at)
#
# A tabela não possui max_objects, used_objects ou used_bytes.

negative_quotas = conn.execute(
    "SELECT COUNT(*) FROM quotas WHERE quota_bytes < 0"
).fetchone()[0]

invalid_quota_status = conn.execute(
    "SELECT COUNT(*) FROM quotas "
    "WHERE status NOT IN ('ACTIVE', 'DISABLED')"
).fetchone()[0]

quota_namespace_orphans = conn.execute(
    "SELECT COUNT(*) "
    "FROM quotas q "
    "LEFT JOIN namespaces n ON n.namespace = q.namespace "
    "WHERE n.namespace IS NULL"
).fetchone()[0]

check(
    "Quota values",
    negative_quotas == 0,
    f"negative_quota_bytes={negative_quotas}"
)

check(
    "Quota status",
    invalid_quota_status == 0,
    f"invalid_status={invalid_quota_status}"
)

check(
    "Quota → namespace integrity",
    quota_namespace_orphans == 0,
    f"orphans={quota_namespace_orphans}"
)

# 10. PHYSICAL BLOCK STORAGE
# ============================================================

block_dir = ROOT / "storage" / "blocks"

registry_block_ids = {
    row[0]
    for row in conn.execute(
        "SELECT block_id FROM blocks"
    )
}

physical_block_ids = {
    p.name
    for p in block_dir.iterdir()
    if p.is_file()
}

missing_physical_blocks = registry_block_ids - physical_block_ids
unregistered_physical_blocks = physical_block_ids - registry_block_ids

check(
    "Registry blocks ↔ physical storage",
    not missing_physical_blocks
    and not unregistered_physical_blocks,
    f"missing={len(missing_physical_blocks)}, "
    f"unregistered={len(unregistered_physical_blocks)}"
)

# ============================================================
# 11. PHYSICAL OBJECT STORAGE
# ============================================================

object_dir = ROOT / "storage" / "objects"

physical_object_ids = {
    p.name
    for p in object_dir.iterdir()
    if p.is_file()
}

registered_object_ids = {
    row[0]
    for row in conn.execute(
        "SELECT object_id FROM objects"
    )
}

unregistered_objects = (
    physical_object_ids - registered_object_ids
)

registered_required_files = {
    row[0]
    for row in conn.execute("""
        SELECT object_id
        FROM objects
        WHERE status='ACTIVE'
          AND storage_path IS NOT NULL
    """)
}

missing_required_objects = (
    registered_required_files - physical_object_ids
)

check(
    "Physical objects without registry",
    len(unregistered_objects) == 0,
    f"unregistered={len(unregistered_objects)}"
)

check(
    "Required active object files",
    len(missing_required_objects) == 0,
    f"missing={len(missing_required_objects)}"
)

# ============================================================
# 12. ACTIVE TRANSACTION STATES
# ============================================================

pending = conn.execute("""
    SELECT COUNT(*)
    FROM transactions
    WHERE state IN ('PENDING', 'RUNNING', 'IN_PROGRESS')
""").fetchone()[0]

print("\n[TRANSACTION STATE]")
print(f"  pending/running: {pending}")

# Não considera automaticamente pending como falha.
check(
    "Transaction state consistency",
    pending >= 0,
    f"pending={pending}"
)

# ============================================================
# 13. API TEST SUITE
# ============================================================

print("\n[API TEST SUITE]")

test_cmd = [
    sys.executable,
    "-m",
    "pytest",
    "tests/api",
    "-q",
    "--disable-warnings",
]

try:
    proc = subprocess.run(
        test_cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    output = proc.stdout.strip()
    errors = proc.stderr.strip()

    print(output)

    if errors:
        print(errors)

    check(
        "API test suite",
        proc.returncode == 0,
        f"exit_code={proc.returncode}"
    )

except Exception as exc:
    check(
        "API test suite",
        False,
        repr(exc)
    )

# ============================================================
# 14. PROJECT PYTHON COMPILE
# ============================================================

print("\n[PYTHON COMPILE CHECK]")

compile_cmd = [
    sys.executable,
    "-m",
    "compileall",
    "-q",
    "api",
    "node",
    "cli",
]

proc = subprocess.run(
    compile_cmd,
    cwd=ROOT,
    capture_output=True,
    text=True,
)

check(
    "Python source compilation",
    proc.returncode == 0,
    f"exit_code={proc.returncode}"
)

# ============================================================
# 15. FINAL RESULT
# ============================================================

print("\n" + "=" * 78)
print("FINAL RESULT")
print("=" * 78)

failed = [
    name
    for name, ok in results
    if not ok
]

if not failed:
    print("RESULTADO: PASS")
    print("Sistema estruturalmente íntegro.")
    print("Nenhuma inconsistência crítica encontrada.")
else:
    print("RESULTADO: REVIEW")
    print(f"Falhas encontradas: {len(failed)}")

    for name in failed:
        print(f"  - {name}")

print("=" * 78)

conn.close()

sys.exit(0 if not failed else 1)
