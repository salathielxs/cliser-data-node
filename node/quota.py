from node.registry import connect
from node.capacity import can_allocate
from node.accounting import namespace_accounting


QUOTA_MODES = {
    "LOGICAL",
    "PHYSICAL",
    "HYBRID",
}


def ensure_default_quota():
    conn = connect()

    row = conn.execute("""
        SELECT namespace
        FROM quotas
        WHERE namespace = 'default'
    """).fetchone()

    if row is None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()

        conn.execute("""
            INSERT INTO quotas (
                namespace,
                quota_bytes,
                status,
                created_at
            )
            VALUES (?, ?, 'ACTIVE', ?)
        """, ("default", 0, now))

        conn.commit()

    conn.close()


def get_quota(namespace="default"):
    conn = connect()

    row = conn.execute("""
        SELECT
            namespace,
            quota_bytes,
            status,
            created_at
        FROM quotas
        WHERE namespace = ?
    """, (namespace,)).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "namespace": row[0],
        "quota_bytes": row[1],
        "status": row[2],
        "created_at": row[3],
    }


def register_quota(namespace, quota_bytes):
    if not namespace:
        raise ValueError("namespace inválido.")

    if quota_bytes < 0:
        raise ValueError("quota inválida.")

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    conn.execute("""
        INSERT INTO quotas (
            namespace,
            quota_bytes,
            status,
            created_at
        )
        VALUES (?, ?, 'ACTIVE', ?)
        ON CONFLICT(namespace)
        DO UPDATE SET
            quota_bytes = excluded.quota_bytes,
            status = 'ACTIVE'
    """, (
        namespace,
        quota_bytes,
        now,
    ))

    conn.commit()
    conn.close()


def set_quota(namespace, quota_bytes):
    register_quota(namespace, quota_bytes)


def list_quotas():
    conn = connect()

    rows = conn.execute("""
        SELECT
            namespace,
            quota_bytes,
            status,
            created_at
        FROM quotas
        ORDER BY namespace
    """).fetchall()

    conn.close()

    return [
        {
            "namespace": row[0],
            "quota_bytes": row[1],
            "status": row[2],
            "created_at": row[3],
        }
        for row in rows
    ]


def namespace_usage(namespace):
    if not namespace:
        raise ValueError("namespace inválido.")

    conn = connect()

    logical_bytes = conn.execute("""
        SELECT COALESCE(SUM(size), 0)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()[0]

    conn.close()

    return logical_bytes


def physical_namespace_usage(namespace):
    """
    Retorna o custo físico atribuído ao namespace
    após deduplicação.
    """

    report = namespace_accounting(namespace)

    return report["accounting"]["attributed_physical_bytes"]


def quota_usage(namespace, mode="LOGICAL"):
    mode = mode.upper()

    if mode not in QUOTA_MODES:
        raise ValueError(
            f"Modo de quota inválido: {mode}. "
            f"Use: {', '.join(sorted(QUOTA_MODES))}"
        )

    report = namespace_accounting(namespace)

    logical = report["accounting"]["logical_bytes"]
    physical = report["accounting"]["attributed_physical_bytes"]

    if mode == "LOGICAL":
        return logical

    if mode == "PHYSICAL":
        return physical

    # HYBRID:
    # mantém o maior consumo como referência conservadora.
    return max(logical, physical)


def can_allocate_quota(
    required_bytes,
    namespace="default",
    mode="LOGICAL",
):
    if required_bytes < 0:
        raise ValueError("required_bytes inválido.")

    quota = get_quota(namespace)

    if quota is None:
        return {
            "allowed": False,
            "reason": "QUOTA_NOT_CONFIGURED",
        }

    if quota["status"] != "ACTIVE":
        return {
            "allowed": False,
            "reason": "QUOTA_INACTIVE",
        }

    quota_bytes = quota["quota_bytes"]

    # 0 = ilimitado
    if quota_bytes == 0:
        return {
            "allowed": True,
            "reason": "UNLIMITED",
        }

    current_usage = quota_usage(
        namespace,
        mode=mode,
    )

    available = max(
        quota_bytes - current_usage,
        0,
    )

    if required_bytes > available:
        return {
            "allowed": False,
            "reason": "QUOTA_EXCEEDED",
            "mode": mode,
            "quota_bytes": quota_bytes,
            "used_bytes": current_usage,
            "available_bytes": available,
            "required_bytes": required_bytes,
        }

    return {
        "allowed": True,
        "reason": "OK",
        "mode": mode,
        "quota_bytes": quota_bytes,
        "used_bytes": current_usage,
        "available_bytes": available,
        "required_bytes": required_bytes,
    }


def can_allocate_physical(
    required_bytes,
    namespace="default",
):
    """
    Verificação física conservadora.

    Não tenta adivinhar a deduplicação futura.
    O objetivo nesta fase é disponibilizar
    a contabilidade física para o enforcement.
    """

    return can_allocate_quota(
        required_bytes,
        namespace=namespace,
        mode="PHYSICAL",
    )


def quota_status(namespace="default", mode="LOGICAL"):
    quota = get_quota(namespace)

    if quota is None:
        return {
            "namespace": namespace,
            "quota_bytes": 0,
            "used_bytes": 0,
            "available_bytes": 0,
            "state": "UNCONFIGURED",
            "mode": mode,
        }

    used = quota_usage(
        namespace,
        mode=mode,
    )

    limit = quota["quota_bytes"]

    if limit == 0:
        available = None
        state = "ACTIVE"
    else:
        available = max(limit - used, 0)

        if used >= limit:
            state = "EXHAUSTED"
        else:
            state = "ACTIVE"

    return {
        "namespace": namespace,
        "quota_bytes": limit,
        "used_bytes": used,
        "available_bytes": available,
        "state": state,
        "mode": mode,
    }


def quota_report(namespace="default", mode="LOGICAL"):
    return quota_status(
        namespace,
        mode=mode,
    )
