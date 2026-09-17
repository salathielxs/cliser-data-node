from node.quota import (
    ensure_default_quota,
    get_quota,
    set_quota,
    quota_usage,
    quota_status,
    can_allocate_quota,
    QUOTA_MODES,
)


def ensure_test_namespace(namespace):
    from node.registry import connect
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


def cleanup_namespace(namespace):
    from node.registry import connect

    conn = connect()

    conn.execute(
        "DELETE FROM quotas WHERE namespace = ?",
        (namespace,),
    )

    conn.execute(
        "DELETE FROM namespaces WHERE namespace = ?",
        (namespace,),
    )

    conn.commit()
    conn.close()


def test_default_quota():
    ensure_default_quota()

    quota = get_quota("default")

    assert quota is not None
    assert quota["namespace"] == "default"
    assert quota["status"] == "ACTIVE"

    print("DEFAULT QUOTA: OK")


def test_quota_unlimited():
    namespace = "test_unlimited"

    cleanup_namespace(namespace)
    ensure_test_namespace(namespace)
    set_quota(namespace, 0)

    result = can_allocate_quota(
        10**12,
        namespace=namespace,
        mode="LOGICAL",
    )

    assert result["allowed"] is True
    assert result["reason"] == "UNLIMITED"

    print("UNLIMITED QUOTA: OK")

    cleanup_namespace(namespace)


def test_quota_exceeded():
    namespace = "test_exceeded"

    cleanup_namespace(namespace)
    ensure_test_namespace(namespace)

    set_quota(
        namespace,
        1000,
    )

    result = can_allocate_quota(
        1001,
        namespace=namespace,
        mode="LOGICAL",
    )

    assert result["allowed"] is False
    assert result["reason"] == "QUOTA_EXCEEDED"
    assert result["quota_bytes"] == 1000
    assert result["used_bytes"] == 0
    assert result["available_bytes"] == 1000

    print("QUOTA EXCEEDED: OK")

    cleanup_namespace(namespace)


def test_quota_available():
    namespace = "test_available"

    cleanup_namespace(namespace)
    ensure_test_namespace(namespace)

    set_quota(
        namespace,
        1000,
    )

    result = can_allocate_quota(
        500,
        namespace=namespace,
        mode="LOGICAL",
    )

    assert result["allowed"] is True
    assert result["reason"] == "OK"
    assert result["available_bytes"] == 1000
    assert result["required_bytes"] == 500

    print("QUOTA AVAILABLE: OK")

    cleanup_namespace(namespace)


def test_modes():
    assert "LOGICAL" in QUOTA_MODES
    assert "PHYSICAL" in QUOTA_MODES
    assert "HYBRID" in QUOTA_MODES

    print("QUOTA MODES: OK")


def test_namespace_isolation():
    namespace_a = "test_namespace_a"
    namespace_b = "test_namespace_b"

    cleanup_namespace(namespace_a)
    cleanup_namespace(namespace_b)

    ensure_test_namespace(namespace_a)
    ensure_test_namespace(namespace_b)

    set_quota(
        namespace_a,
        1000,
    )

    set_quota(
        namespace_b,
        2000,
    )

    status_a = quota_status(
        namespace_a,
        mode="LOGICAL",
    )

    status_b = quota_status(
        namespace_b,
        mode="LOGICAL",
    )

    assert status_a["quota_bytes"] == 1000
    assert status_b["quota_bytes"] == 2000

    assert status_a["namespace"] != status_b["namespace"]

    print("NAMESPACE ISOLATION: OK")

    cleanup_namespace(namespace_a)
    cleanup_namespace(namespace_b)


def test_unconfigured_namespace():
    namespace = "test_unconfigured"

    cleanup_namespace(namespace)

    result = can_allocate_quota(
        100,
        namespace=namespace,
        mode="LOGICAL",
    )

    assert result["allowed"] is False
    assert result["reason"] == "QUOTA_NOT_CONFIGURED"

    print("UNCONFIGURED QUOTA: OK")


if __name__ == "__main__":
    print("=" * 60)
    print("QUOTA TEST")
    print("=" * 60)

    test_default_quota()
    test_quota_unlimited()
    test_quota_exceeded()
    test_quota_available()
    test_modes()
    test_namespace_isolation()
    test_unconfigured_namespace()

    print("=" * 60)
    print("QUOTA: OK")
    print("=" * 60)
