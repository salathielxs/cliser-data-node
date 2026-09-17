from node.registry import connect
from node.capacity import storage_capacity


def namespace_accounting(namespace):
    if not namespace:
        raise ValueError("namespace inválido.")

    conn = connect()

    ns = conn.execute("""
        SELECT namespace, status, quota_bytes
        FROM namespaces
        WHERE namespace = ?
    """, (namespace,)).fetchone()

    if ns is None:
        conn.close()
        raise ValueError(f"Namespace inexistente: {namespace}")

    namespace_name, status, quota_bytes = ns

    # Objetos lógicos ativos
    objects = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0),
            COALESCE(SUM(
                CASE
                    WHEN storage_path IS NOT NULL THEN size
                    ELSE 0
                END
            ), 0)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()

    object_count = objects[0]
    logical_bytes = objects[1]
    direct_bytes = objects[2]

    # Blocos referenciados pelo namespace.
    rows = conn.execute("""
        SELECT
            mb.block_id,
            b.size,
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

    unique_blocks = {}

    for block_id, physical_size, global_ref_count in rows:
        if block_id not in unique_blocks:
            unique_blocks[block_id] = {
                "size": physical_size,
                "global_refs": max(global_ref_count, 1),
                "namespace_refs": 0,
            }

        unique_blocks[block_id]["namespace_refs"] += 1

    unique_block_count = len(unique_blocks)

    unique_physical_bytes = sum(
        block["size"]
        for block in unique_blocks.values()
    )

    attributed_block_bytes = 0

    for block in unique_blocks.values():
        attributed_block_bytes += int(
            block["size"]
            * block["namespace_refs"]
            / block["global_refs"]
        )

    attributed_physical_bytes = (
        direct_bytes + attributed_block_bytes
    )

    savings_bytes = max(
        logical_bytes - attributed_physical_bytes,
        0,
    )

    ratio = (
        logical_bytes / attributed_physical_bytes
        if attributed_physical_bytes
        else 1.0
    )

    # Quota atual continua sendo lógica.
    quota_available = (
        None
        if quota_bytes == 0
        else max(quota_bytes - logical_bytes, 0)
    )

    conn.close()

    return {
        "namespace": namespace_name,
        "status": status,

        "objects": {
            "count": object_count,
            "logical_bytes": logical_bytes,
            "direct_bytes": direct_bytes,
        },

        "blocks": {
            "references": references,
            "unique": unique_block_count,
            "unique_physical_bytes": unique_physical_bytes,
            "attributed_physical_bytes": attributed_block_bytes,
        },

        "accounting": {
            "logical_bytes": logical_bytes,
            "attributed_physical_bytes": attributed_physical_bytes,
            "dedup_savings_bytes": savings_bytes,
            "dedup_ratio": round(ratio, 4),
        },

        "quota": {
            "quota_bytes": quota_bytes,
            "used_logical_bytes": logical_bytes,
            "available_logical_bytes": quota_available,
        },
    }


def global_accounting():
    conn = connect()

    row = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
    """).fetchone()

    object_count = row[0]
    logical_bytes = row[1]

    direct = conn.execute("""
        SELECT COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
          AND storage_path IS NOT NULL
    """).fetchone()[0]

    blocks = conn.execute("""
        SELECT COALESCE(SUM(size), 0)
        FROM blocks
        WHERE status = 'ACTIVE'
    """).fetchone()[0]

    referenced = conn.execute("""
        SELECT COALESCE(SUM(size), 0)
        FROM manifest_blocks mb
        JOIN manifests m
          ON m.object_id = mb.object_id
        WHERE m.status = 'ACTIVE'
    """).fetchone()[0]

    conn.close()

    physical_payload = direct + blocks

    savings = max(
        logical_bytes - physical_payload,
        0,
    )

    ratio = (
        logical_bytes / physical_payload
        if physical_payload
        else 1.0
    )

    capacity = storage_capacity()

    return {
        "objects": {
            "count": object_count,
            "logical_bytes": logical_bytes,
        },

        "physical": {
            "direct_bytes": direct,
            "block_bytes": blocks,
            "payload_bytes": physical_payload,
        },

        "references": {
            "logical_block_references": referenced,
        },

        "accounting": {
            "logical_bytes": logical_bytes,
            "physical_payload_bytes": physical_payload,
            "dedup_savings_bytes": savings,
            "dedup_ratio": round(ratio, 4),
        },

        "capacity": {
            "state": capacity["cliser_capacity"]["state"],
            "free_bytes": capacity["cliser_capacity"]["free_bytes"],
            "capacity_bytes": capacity["cliser_capacity"]["capacity_bytes"],
        },
    }


def format_accounting(report):
    namespace = report["namespace"]

    o = report["objects"]
    b = report["blocks"]
    a = report["accounting"]
    q = report["quota"]

    lines = [
        "=== CLISER ACCOUNTING ===",
        "",
        f"Namespace: {namespace}",
        f"Status:    {report['status']}",
        "",
        "OBJECTS",
        f"Count:              {o['count']}",
        f"Logical:            {o['logical_bytes']} bytes",
        f"Direct:             {o['direct_bytes']} bytes",
        "",
        "BLOCKS",
        f"References:         {b['references']}",
        f"Unique:              {b['unique']}",
        f"Unique Physical:    {b['unique_physical_bytes']} bytes",
        f"Attributed Physical:{b['attributed_physical_bytes']} bytes",
        "",
        "ACCOUNTING",
        f"Logical:            {a['logical_bytes']} bytes",
        f"Physical Attributed:{a['attributed_physical_bytes']} bytes",
        f"Dedup Savings:      {a['dedup_savings_bytes']} bytes",
        f"Dedup Ratio:        {a['dedup_ratio']}x",
        "",
        "QUOTA",
        (
            "Quota:              UNLIMITED"
            if q["quota_bytes"] == 0
            else f"Quota:              {q['quota_bytes']} bytes"
        ),
        f"Logical Used:       {q['used_logical_bytes']} bytes",
        (
            "Logical Available:  UNLIMITED"
            if q["available_logical_bytes"] is None
            else f"Logical Available:  {q['available_logical_bytes']} bytes"
        ),
    ]

    return "\n".join(lines)
