import hashlib

from node.registry import connect
from node.capacity import filesystem_capacity


DEFAULT_BLOCK_SIZE = 1024 * 1024


def _capacity_policy():
    from node.capacity import load_policy

    return load_policy().get("policy", {})


def _metadata_overhead(
    object_count=1,
    new_block_count=0,
):
    policy = _capacity_policy()

    per_object = int(
        policy.get(
            "metadata_overhead_per_object_bytes",
            4096,
        )
    )

    per_block = int(
        policy.get(
            "metadata_overhead_per_block_bytes",
            512,
        )
    )

    object_metadata_bytes = (
        object_count * per_object
    )

    block_metadata_bytes = (
        new_block_count * per_block
    )

    return {
        "object_metadata_bytes": object_metadata_bytes,
        "block_metadata_bytes": block_metadata_bytes,
        "metadata_overhead_bytes": (
            object_metadata_bytes
            + block_metadata_bytes
        ),
    }


def _safety_overhead():
    policy = _capacity_policy()

    return int(
        policy.get(
            "filesystem_safety_bytes",
            0,
        )
    )


def calculate_block_plan(
    data: bytes,
    block_size=DEFAULT_BLOCK_SIZE,
):
    if not isinstance(data, bytes):
        raise TypeError("data deve ser bytes.")

    if block_size <= 0:
        raise ValueError("block_size inválido.")

    blocks = []

    for index, offset in enumerate(
        range(0, len(data), block_size)
    ):
        chunk = data[
            offset:offset + block_size
        ]

        block_id = hashlib.sha256(
            chunk
        ).hexdigest()

        blocks.append(
            {
                "index": index,
                "block_id": block_id,
                "size": len(chunk),
            }
        )

    conn = connect()

    new_blocks = []
    existing_blocks = []

    for block in blocks:
        row = conn.execute(
            """
            SELECT
                block_id,
                size,
                status
            FROM blocks
            WHERE block_id = ?
            """,
            (block["block_id"],),
        ).fetchone()

        if row is None or row[2] != "ACTIVE":
            new_blocks.append(block)
        else:
            existing_blocks.append(block)

    conn.close()

    new_block_bytes = sum(
        block["size"]
        for block in new_blocks
    )

    existing_block_bytes = sum(
        block["size"]
        for block in existing_blocks
    )

    overhead = _metadata_overhead(
        object_count=1,
        new_block_count=len(new_blocks),
    )

    safety_bytes = _safety_overhead()

    required_physical_bytes = (
        new_block_bytes
        + overhead["metadata_overhead_bytes"]
        + safety_bytes
    )

    return {
        "logical_bytes": len(data),

        "block_count": len(blocks),

        "new_blocks": len(new_blocks),

        "existing_blocks": len(existing_blocks),

        "new_block_bytes": new_block_bytes,

        "existing_block_bytes": existing_block_bytes,

        "physical_payload_delta": new_block_bytes,

        "object_metadata_bytes": (
            overhead["object_metadata_bytes"]
        ),

        "block_metadata_bytes": (
            overhead["block_metadata_bytes"]
        ),

        "metadata_overhead_bytes": (
            overhead["metadata_overhead_bytes"]
        ),

        "filesystem_safety_bytes": safety_bytes,

        "required_physical_bytes": (
            required_physical_bytes
        ),

        "blocks": blocks,
    }


def estimate_direct_allocation(
    data: bytes,
    namespace: str = "default",
):
    if not isinstance(data, bytes):
        raise TypeError("data deve ser bytes.")

    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace inválido.")

    from node.namespace_manager import require_namespace

    require_namespace(namespace)

    content_hash = hashlib.sha256(
        data
    ).hexdigest()

    conn = connect()

    try:
        row = conn.execute(
            """
            SELECT
                object_id,
                content_hash,
                size,
                status
            FROM objects
            WHERE namespace = ?
              AND content_hash = ?
              AND status = 'ACTIVE'
            LIMIT 1
            """,
            (
                namespace,
                content_hash,
            ),
        ).fetchone()
    finally:
        conn.close()

    if row is not None:
        overhead = _metadata_overhead(
            object_count=0,
            new_block_count=0,
        )

        return {
            "logical_bytes": len(data),

            "physical_payload_delta": 0,

            "already_exists": True,

            "object_id": row[0],

            "content_hash": content_hash,

            "namespace": namespace,

            "object_metadata_bytes": 0,

            "block_metadata_bytes": 0,

            "metadata_overhead_bytes": 0,

            "filesystem_safety_bytes": 0,

            "required_physical_bytes": 0,
        }

    overhead = _metadata_overhead(
        object_count=1,
        new_block_count=0,
    )

    safety_bytes = _safety_overhead()

    required_physical_bytes = (
        len(data)
        + overhead["metadata_overhead_bytes"]
        + safety_bytes
    )

    return {
        "logical_bytes": len(data),

        "physical_payload_delta": len(data),

        "already_exists": False,

        "object_id": None,

        "content_hash": content_hash,

        "namespace": namespace,

        "object_metadata_bytes": (
            overhead["object_metadata_bytes"]
        ),

        "block_metadata_bytes": (
            overhead["block_metadata_bytes"]
        ),

        "metadata_overhead_bytes": (
            overhead["metadata_overhead_bytes"]
        ),

        "filesystem_safety_bytes": safety_bytes,

        "required_physical_bytes": (
            required_physical_bytes
        ),
    }


def estimate_allocation(
    data: bytes,
    block_size=DEFAULT_BLOCK_SIZE,
    block_mode=False,
    namespace="default",
):
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace inválido.")

    if block_mode:
        allocation = calculate_block_plan(
            data,
            block_size=block_size,
        )
        allocation["namespace"] = namespace
        return allocation

    return estimate_direct_allocation(
        data,
        namespace=namespace,
    )


def check_global_capacity(
    required_bytes,
):
    capacity = filesystem_capacity()

    available = capacity["free_bytes"]

    return {
        "allowed": (
            required_bytes <= available
        ),

        "required_bytes": required_bytes,

        "available_bytes": available,

        "state": (
            "ALLOW"
            if required_bytes <= available
            else "DENY"
        ),
    }


def check_allocation_capacity(
    allocation,
):
    required = allocation.get(
        "required_physical_bytes",
        allocation.get(
            "physical_payload_delta",
            0,
        ),
    )

    result = check_global_capacity(
        required
    )

    return {
        **result,
        "payload_bytes": allocation.get(
            "physical_payload_delta",
            0,
        ),
        "metadata_bytes": allocation.get(
            "metadata_overhead_bytes",
            0,
        ),
        "safety_bytes": allocation.get(
            "filesystem_safety_bytes",
            0,
        ),
    }
