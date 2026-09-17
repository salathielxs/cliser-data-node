from node.registry import connect
from node.capacity import storage_capacity
from node.quota import quota_report


def _namespace_block_metrics(conn, namespace):
    rows = conn.execute("""
        SELECT
            mb.block_id,
            mb.size,
            b.size AS physical_size,
            b.ref_count
        FROM manifest_blocks mb
        JOIN manifests m
          ON m.object_id = mb.object_id
        JOIN blocks b
          ON b.block_id = mb.block_id
        WHERE m.namespace = ?
          AND m.status = 'ACTIVE'
          AND b.status = 'ACTIVE'
    """, (namespace,)).fetchall()

    references = len(rows)
    referenced_bytes = sum(row[1] for row in rows)

    unique_blocks = {}

    for block_id, logical_size, physical_size, ref_count in rows:
        if block_id not in unique_blocks:
            unique_blocks[block_id] = {
                "size": physical_size,
                "ref_count": ref_count,
                "namespace_refs": 0,
            }

        unique_blocks[block_id]["namespace_refs"] += 1

    unique_physical_bytes = sum(
        block["size"]
        for block in unique_blocks.values()
    )

    shared_blocks = sum(
        1
        for block in unique_blocks.values()
        if block["ref_count"] > 1
    )

    attributed_physical_bytes = 0.0

    for block in unique_blocks.values():
        global_refs = max(block["ref_count"], 1)
        namespace_refs = block["namespace_refs"]

        attributed_physical_bytes += (
            block["size"]
            * namespace_refs
            / global_refs
        )

    savings = max(
        referenced_bytes - attributed_physical_bytes,
        0,
    )

    if attributed_physical_bytes:
        ratio = (
            referenced_bytes
            / attributed_physical_bytes
        )
    else:
        ratio = 1.0

    savings_percent = (
        savings / referenced_bytes * 100
        if referenced_bytes
        else 0
    )

    return {
        "references": references,
        "unique_blocks": len(unique_blocks),
        "referenced_bytes": referenced_bytes,
        "unique_physical_bytes": unique_physical_bytes,
        "attributed_physical_bytes": int(
            attributed_physical_bytes
        ),
        "shared_blocks": shared_blocks,
        "savings_bytes": int(savings),
        "ratio": round(ratio, 4),
        "savings_percent": round(
            savings_percent,
            2,
        ),
    }



def namespace_metrics(namespace):
    if not namespace:
        raise ValueError("Namespace inválido.")

    conn = connect()

    namespace_record = conn.execute("""
        SELECT
            namespace,
            status
        FROM namespaces
        WHERE namespace = ?
    """, (namespace,)).fetchone()

    if namespace_record is None:
        conn.close()
        raise ValueError(
            f"Namespace inexistente: {namespace}"
        )

    objects = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()

    direct = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
          AND storage_path IS NOT NULL
    """, (namespace,)).fetchone()

    block_objects = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
          AND storage_path IS NULL
    """, (namespace,)).fetchone()

    manifests = conn.execute("""
        SELECT COUNT(*)
        FROM manifests
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()[0]

    block_metrics = _namespace_block_metrics(
        conn,
        namespace,
    )

    conn.close()

    quota = quota_report(namespace)
    capacity = storage_capacity()

    logical_bytes = objects[1]
    direct_bytes = direct[1]

    attributed_physical = (
        direct_bytes
        + block_metrics["attributed_physical_bytes"]
    )

    total_savings = max(
        logical_bytes - attributed_physical,
        0,
    )

    if attributed_physical:
        total_ratio = (
            logical_bytes / attributed_physical
        )
    else:
        total_ratio = 1.0

    return {
        "namespace": namespace,
        "status": namespace_record[1],

        "objects": {
            "total": objects[0],
            "direct": direct[0],
            "block": block_objects[0],
            "logical_bytes": logical_bytes,
        },

        "manifests": manifests,

        "blocks": block_metrics,

        "deduplication": {
            "savings_bytes": int(total_savings),
            "ratio": round(total_ratio, 4),
            "savings_percent": round(
                (
                    total_savings
                    / logical_bytes
                    * 100
                )
                if logical_bytes
                else 0,
                2,
            ),
        },

        "quota": quota,

        "capacity": {
            "state": capacity[
                "cliser_capacity"
            ]["state"],
            "free_bytes": capacity[
                "cliser_capacity"
            ]["free_bytes"],
        },
    }


def storage_metrics():
    conn = connect()

    objects = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
    """).fetchone()

    direct = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
          AND storage_path IS NOT NULL
    """).fetchone()

    block_objects = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
          AND storage_path IS NULL
    """).fetchone()

    blocks = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM blocks
        WHERE status = 'ACTIVE'
    """).fetchone()

    references = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM manifest_blocks mb
        JOIN manifests m
          ON m.object_id = mb.object_id
        WHERE m.status = 'ACTIVE'
    """).fetchone()

    shared_blocks = conn.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT block_id
            FROM manifest_blocks mb
            JOIN manifests m
              ON m.object_id = mb.object_id
            WHERE m.status = 'ACTIVE'
            GROUP BY block_id
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    conn.close()

    logical_bytes = objects[1]
    direct_bytes = direct[1]
    block_logical_bytes = block_objects[1]

    physical_block_bytes = blocks[1]
    referenced_block_bytes = references[1]

    dedup_savings = max(
        referenced_block_bytes
        - physical_block_bytes,
        0,
    )

    if physical_block_bytes:
        dedup_ratio = (
            referenced_block_bytes
            / physical_block_bytes
        )
    else:
        dedup_ratio = 1.0

    capacity = storage_capacity()

    return {
        "objects": {
            "total": objects[0],
            "logical_bytes": logical_bytes,
        },

        "direct": {
            "count": direct[0],
            "logical_bytes": direct_bytes,
        },

        "block_objects": {
            "count": block_objects[0],
            "logical_bytes": block_logical_bytes,
        },

        "blocks": {
            "unique": blocks[0],
            "physical_bytes": physical_block_bytes,
            "referenced_bytes": referenced_block_bytes,
            "shared_blocks": shared_blocks,
        },

        "deduplication": {
            "savings_bytes": dedup_savings,
            "ratio": round(
                dedup_ratio,
                4,
            ),
            "savings_percent": round(
                (
                    dedup_savings
                    / referenced_block_bytes
                    * 100
                )
                if referenced_block_bytes
                else 0,
                2,
            ),
        },

        "capacity": capacity,
    }
