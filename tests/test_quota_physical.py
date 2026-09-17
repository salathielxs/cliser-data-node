from node.registry import connect
from node.quota import (
    set_quota,
    quota_usage,
    quota_status,
)
from node.accounting import namespace_accounting
from node.object_manager import put_object


NAMESPACE_A = "test_physical_a"
NAMESPACE_B = "test_physical_b"


def create_namespace(namespace):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    conn.execute(
        """
        INSERT INTO namespaces (
            namespace,
            status,
            quota_bytes,
            created_at,
            updated_at
        )
        VALUES (?, 'ACTIVE', 0, ?, ?)
        ON CONFLICT(namespace)
        DO UPDATE SET
            status = 'ACTIVE',
            updated_at = excluded.updated_at
        """,
        (namespace, now, now),
    )

    conn.commit()
    conn.close()


def cleanup():
    conn = connect()

    # Descobrir objetos dos namespaces de teste.
    rows = conn.execute(
        """
        SELECT object_id
        FROM objects
        WHERE namespace IN (?, ?)
        """,
        (NAMESPACE_A, NAMESPACE_B),
    ).fetchall()

    object_ids = [row[0] for row in rows]

    # Remover referências dos manifests.
    for object_id in object_ids:
        conn.execute(
            "DELETE FROM manifest_blocks WHERE object_id = ?",
            (object_id,),
        )

        conn.execute(
            "DELETE FROM manifests WHERE object_id = ?",
            (object_id,),
        )

        conn.execute(
            "DELETE FROM objects WHERE object_id = ?",
            (object_id,),
        )

    conn.execute(
        "DELETE FROM quotas WHERE namespace IN (?, ?)",
        (NAMESPACE_A, NAMESPACE_B),
    )

    conn.execute(
        "DELETE FROM namespaces WHERE namespace IN (?, ?)",
        (NAMESPACE_A, NAMESPACE_B),
    )

    conn.commit()
    conn.close()


def test_shared_block_physical_accounting():
    cleanup()

    create_namespace(NAMESPACE_A)
    create_namespace(NAMESPACE_B)

    set_quota(NAMESPACE_A, 0)
    set_quota(NAMESPACE_B, 0)

    data = (
        b"CLISER-SHARED-BLOCK-"
        * 100
    )

    result_a = put_object(
        data,
        namespace=NAMESPACE_A,
    )

    result_b = put_object(
        data,
        namespace=NAMESPACE_B,
    )

    object_a = result_a["object_id"]
    object_b = result_b["object_id"]

    assert object_a != object_b

    # Identidades lógicas diferentes devem apontar
    # para o mesmo conteúdo criptográfico.
    assert result_a["content_hash"] == result_b["content_hash"]

    # Os dois objetos devem reconstruir exatamente
    # o mesmo conteúdo.
    from node.object_manager import get_object_data

    assert get_object_data(object_a) == data
    assert get_object_data(object_b) == data

    report_a = namespace_accounting(
        NAMESPACE_A
    )

    report_b = namespace_accounting(
        NAMESPACE_B
    )

    physical_a = quota_usage(
        NAMESPACE_A,
        mode="PHYSICAL",
    )

    physical_b = quota_usage(
        NAMESPACE_B,
        mode="PHYSICAL",
    )

    logical_a = quota_usage(
        NAMESPACE_A,
        mode="LOGICAL",
    )

    logical_b = quota_usage(
        NAMESPACE_B,
        mode="LOGICAL",
    )

    print()
    print("=== NAMESPACE A ===")
    print("Logical:", logical_a)
    print("Physical:", physical_a)
    print("Unique blocks:",
          report_a["blocks"]["unique"])
    print("Attributed:",
          report_a["blocks"]["attributed_physical_bytes"])

    print()
    print("=== NAMESPACE B ===")
    print("Logical:", logical_b)
    print("Physical:", physical_b)
    print("Unique blocks:",
          report_b["blocks"]["unique"])
    print("Attributed:",
          report_b["blocks"]["attributed_physical_bytes"])

    assert logical_a == len(data)
    assert logical_b == len(data)

    assert physical_a > 0
    assert physical_b > 0

    # O mesmo bloco físico é compartilhado.
    assert (
        physical_a + physical_b
        == len(data)
    )

    print()
    print("SHARED BLOCK DEDUP: OK")

    cleanup()


def test_quota_modes():
    create_namespace(NAMESPACE_A)

    set_quota(
        NAMESPACE_A,
        1000000,
    )

    logical = quota_usage(
        NAMESPACE_A,
        mode="LOGICAL",
    )

    physical = quota_usage(
        NAMESPACE_A,
        mode="PHYSICAL",
    )

    hybrid = quota_usage(
        NAMESPACE_A,
        mode="HYBRID",
    )

    assert hybrid == max(
        logical,
        physical,
    )

    status = quota_status(
        NAMESPACE_A,
        mode="HYBRID",
    )

    assert status["mode"] == "HYBRID"

    print("LOGICAL / PHYSICAL / HYBRID: OK")

    cleanup()


if __name__ == "__main__":
    print("=" * 60)
    print("QUOTA PHYSICAL / DEDUP TEST")
    print("=" * 60)

    test_shared_block_physical_accounting()
    test_quota_modes()

    print("=" * 60)
    print("QUOTA PHYSICAL: OK")
    print("=" * 60)
