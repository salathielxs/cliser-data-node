import re
from datetime import datetime, timezone

from node.registry import connect

VALID_NAMESPACE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

ACTIVE = "ACTIVE"
DISABLED = "DISABLED"


def _now():
    return datetime.now(timezone.utc).isoformat()


def validate_namespace(namespace: str) -> str:
    if not isinstance(namespace, str):
        raise TypeError("namespace deve ser string.")

    namespace = namespace.strip().lower()

    if not namespace:
        raise ValueError("namespace vazio.")

    if not VALID_NAMESPACE.fullmatch(namespace):
        raise ValueError(
            "namespace inválido. Use apenas a-z, 0-9, '.', '_' e '-'."
        )

    return namespace


def namespace_exists(namespace: str) -> bool:
    namespace = validate_namespace(namespace)

    conn = connect()
    try:
        row = conn.execute(
            "SELECT 1 FROM namespaces WHERE namespace = ?",
            (namespace,),
        ).fetchone()

        return row is not None
    finally:
        conn.close()


def create_namespace(
    namespace: str,
    quota_bytes: int = 0,
):
    namespace = validate_namespace(namespace)

    if not isinstance(quota_bytes, int):
        raise TypeError("quota_bytes deve ser inteiro.")

    if quota_bytes < 0:
        raise ValueError("quota_bytes não pode ser negativo.")

    now = _now()

    conn = connect()

    try:
        conn.execute("BEGIN")

        existing = conn.execute(
            "SELECT status FROM namespaces WHERE namespace = ?",
            (namespace,),
        ).fetchone()

        if existing is not None:
            raise ValueError(
                f"namespace já existe: {namespace}"
            )

        conn.execute(
            """
            INSERT INTO namespaces (
                namespace,
                status,
                quota_bytes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                namespace,
                ACTIVE,
                quota_bytes,
                now,
                now,
            ),
        )

        conn.execute(
            """
            INSERT INTO quotas (
                namespace,
                quota_bytes,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                namespace,
                quota_bytes,
                ACTIVE,
                now,
            ),
        )

        conn.commit()

        return get_namespace(namespace)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_namespace(namespace: str):
    namespace = validate_namespace(namespace)

    conn = connect()

    try:
        row = conn.execute(
            """
            SELECT
                namespace,
                status,
                quota_bytes,
                created_at,
                updated_at
            FROM namespaces
            WHERE namespace = ?
            """,
            (namespace,),
        ).fetchone()

        if row is None:
            return None

        return {
            "namespace": row[0],
            "status": row[1],
            "quota_bytes": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }

    finally:
        conn.close()


def list_namespaces(status=None):
    conn = connect()

    try:
        if status is None:
            rows = conn.execute(
                """
                SELECT
                    namespace,
                    status,
                    quota_bytes,
                    created_at,
                    updated_at
                FROM namespaces
                ORDER BY namespace
                """
            ).fetchall()
        else:
            if status not in {ACTIVE, DISABLED}:
                raise ValueError("status inválido.")

            rows = conn.execute(
                """
                SELECT
                    namespace,
                    status,
                    quota_bytes,
                    created_at,
                    updated_at
                FROM namespaces
                WHERE status = ?
                ORDER BY namespace
                """,
                (status,),
            ).fetchall()

        return [
            {
                "namespace": row[0],
                "status": row[1],
                "quota_bytes": row[2],
                "created_at": row[3],
                "updated_at": row[4],
            }
            for row in rows
        ]

    finally:
        conn.close()


def set_namespace_status(namespace: str, status: str):
    namespace = validate_namespace(namespace)

    if status not in {ACTIVE, DISABLED}:
        raise ValueError("status inválido.")

    now = _now()

    conn = connect()

    try:
        conn.execute("BEGIN")

        result = conn.execute(
            """
            UPDATE namespaces
            SET
                status = ?,
                updated_at = ?
            WHERE namespace = ?
            """,
            (
                status,
                now,
                namespace,
            ),
        )

        if result.rowcount == 0:
            raise KeyError(
                f"namespace não encontrado: {namespace}"
            )

        conn.execute(
            """
            UPDATE quotas
            SET status = ?
            WHERE namespace = ?
            """,
            (
                status,
                namespace,
            ),
        )

        conn.commit()

        return get_namespace(namespace)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def enable_namespace(namespace: str):
    return set_namespace_status(namespace, ACTIVE)


def disable_namespace(namespace: str):
    return set_namespace_status(namespace, DISABLED)


def set_namespace_quota(namespace: str, quota_bytes: int):
    namespace = validate_namespace(namespace)

    if not isinstance(quota_bytes, int):
        raise TypeError("quota_bytes deve ser inteiro.")

    if quota_bytes < 0:
        raise ValueError("quota_bytes não pode ser negativo.")

    now = _now()

    conn = connect()

    try:
        conn.execute("BEGIN")

        result = conn.execute(
            """
            UPDATE namespaces
            SET
                quota_bytes = ?,
                updated_at = ?
            WHERE namespace = ?
            """,
            (
                quota_bytes,
                now,
                namespace,
            ),
        )

        if result.rowcount == 0:
            raise KeyError(
                f"namespace não encontrado: {namespace}"
            )

        conn.execute(
            """
            INSERT INTO quotas (
                namespace,
                quota_bytes,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(namespace)
            DO UPDATE SET
                quota_bytes = excluded.quota_bytes,
                status = (
                    SELECT status
                    FROM namespaces
                    WHERE namespaces.namespace = excluded.namespace
                )
            """,
            (
                namespace,
                quota_bytes,
                ACTIVE,
                now,
            ),
        )

        conn.commit()

        return get_namespace(namespace)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def require_namespace(namespace: str, allow_disabled=False):
    info = get_namespace(namespace)

    if info is None:
        raise KeyError(
            f"namespace não encontrado: {namespace}"
        )

    if not allow_disabled and info["status"] != ACTIVE:
        raise PermissionError(
            f"namespace desabilitado: {namespace}"
        )

    return info
