from pathlib import Path

from node.identity import load_identity
from node.registry import (
    connect,
    list_namespace_records,
    all_objects,
    verify_block_ref_counts,
    list_unreferenced_blocks,
)
from node.capacity import allocation_capacity


def _result(status, detail=None, **extra):
    result = {"status": status}

    if detail is not None:
        result["detail"] = detail

    result.update(extra)
    return result


def check_identity():
    try:
        identity = load_identity()

        if not identity:
            return _result(
                "ERROR",
                "Identity vazia."
            )

        return _result(
            "OK",
            "Identity carregada."
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_registry():
    try:
        conn = connect()
        conn.execute("SELECT 1").fetchone()

        tables = {
            row[0]
            for row in conn.execute("""
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
            """).fetchall()
        }

        conn.close()

        required = {
            "namespaces",
            "objects",
            "blocks",
            "manifests",
            "manifest_blocks",
            "quotas",
            "transactions",
            "transaction_journal",
        }

        missing = sorted(required - tables)

        if missing:
            return _result(
                "ERROR",
                "Tabelas obrigatórias ausentes.",
                missing_tables=missing,
            )

        return _result(
            "OK",
            "SQLite operacional.",
            tables=len(tables),
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_namespaces():
    try:
        rows = list_namespace_records()

        active = sum(
            1 for row in rows
            if row["status"] == "ACTIVE"
        )

        disabled = sum(
            1 for row in rows
            if row["status"] == "DISABLED"
        )

        return _result(
            "OK",
            total=len(rows),
            active=active,
            disabled=disabled,
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_objects():
    try:
        rows = all_objects()

        direct = 0
        blocks = 0
        active = 0
        deleted = 0

        for row in rows:
            storage_path = row[3]
            status = row[-1]

            if status == "ACTIVE":
                active += 1

                if storage_path is None:
                    blocks += 1
                else:
                    direct += 1

            elif status == "DELETED":
                deleted += 1

        return _result(
            "OK",
            total=len(rows),
            active=active,
            direct=direct,
            blocks=blocks,
            deleted=deleted,
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_blocks():
    try:
        conn = connect()

        total = conn.execute("""
            SELECT COUNT(*)
            FROM blocks
        """).fetchone()[0]

        active = conn.execute("""
            SELECT COUNT(*)
            FROM blocks
            WHERE status = 'ACTIVE'
        """).fetchone()[0]

        deleted = conn.execute("""
            SELECT COUNT(*)
            FROM blocks
            WHERE status = 'DELETED'
        """).fetchone()[0]

        invalid_refs = conn.execute("""
            SELECT COUNT(*)
            FROM blocks
            WHERE status = 'ACTIVE'
              AND ref_count < 0
        """).fetchone()[0]

        conn.close()

        if invalid_refs:
            return _result(
                "ERROR",
                "Blocks com ref_count inválido.",
                total=total,
                active=active,
                deleted=deleted,
                invalid_ref_counts=invalid_refs,
            )

        return _result(
            "OK",
            total=total,
            active=active,
            deleted=deleted,
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_manifests():
    try:
        conn = connect()

        total = conn.execute("""
            SELECT COUNT(*)
            FROM manifests
        """).fetchone()[0]

        active = conn.execute("""
            SELECT COUNT(*)
            FROM manifests
            WHERE status = 'ACTIVE'
        """).fetchone()[0]

        deleted = conn.execute("""
            SELECT COUNT(*)
            FROM manifests
            WHERE status = 'DELETED'
        """).fetchone()[0]

        orphan_active = conn.execute("""
            SELECT COUNT(*)
            FROM manifests m
            LEFT JOIN objects o
              ON o.object_id = m.object_id
            WHERE m.status = 'ACTIVE'
              AND (
                  o.object_id IS NULL
                  OR o.status != 'ACTIVE'
              )
        """).fetchone()[0]

        invalid_block_counts = conn.execute("""
            SELECT COUNT(*)
            FROM manifests m
            WHERE m.status = 'ACTIVE'
              AND m.block_count != (
                  SELECT COUNT(*)
                  FROM manifest_blocks mb
                  WHERE mb.object_id = m.object_id
              )
        """).fetchone()[0]

        conn.close()

        if orphan_active:
            return _result(
                "ERROR",
                "Manifest ACTIVE sem objeto ACTIVE.",
                total=total,
                active=active,
                deleted=deleted,
                orphan_active=orphan_active,
                invalid_block_counts=invalid_block_counts,
            )

        if invalid_block_counts:
            return _result(
                "ERROR",
                "Manifest com block_count inconsistente.",
                total=total,
                active=active,
                deleted=deleted,
                orphan_active=orphan_active,
                invalid_block_counts=invalid_block_counts,
            )

        return _result(
            "OK",
            total=total,
            active=active,
            deleted=deleted,
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_transactions():
    try:
        conn = connect()

        total = conn.execute("""
            SELECT COUNT(*)
            FROM transactions
        """).fetchone()[0]

        committed = conn.execute("""
            SELECT COUNT(*)
            FROM transactions
            WHERE state = 'COMMITTED'
        """).fetchone()[0]

        failed = conn.execute("""
            SELECT COUNT(*)
            FROM transactions
            WHERE state = 'FAILED'
        """).fetchone()[0]

        pending = conn.execute("""
            SELECT COUNT(*)
            FROM transactions
            WHERE state IN (
                'PREPARED',
                'WRITING',
                'VERIFYING',
                'COMMITTING'
            )
        """).fetchone()[0]

        rollback = conn.execute("""
            SELECT COUNT(*)
            FROM transactions
            WHERE state = 'ROLLBACK'
        """).fetchone()[0]

        terminal = conn.execute("""
            SELECT COUNT(*)
            FROM transactions
            WHERE state IN (
                'COMMITTED',
                'ROLLBACK'
            )
        """).fetchone()[0]

        conn.close()

        status = "WARNING" if pending else "OK"

        return _result(
            status,
            total=total,
            committed=committed,
            failed=failed,
            rollback=rollback,
            pending=pending,
            terminal=terminal,
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_journal():
    try:
        conn = connect()

        total = conn.execute("""
            SELECT COUNT(*)
            FROM transaction_journal
        """).fetchone()[0]

        committed_markers = conn.execute("""
            SELECT COUNT(*)
            FROM transaction_journal
            WHERE commit_marker = 1
        """).fetchone()[0]

        verified = conn.execute("""
            SELECT COUNT(*)
            FROM transaction_journal
            WHERE verified = 1
        """).fetchone()[0]

        pending = conn.execute("""
            SELECT COUNT(*)
            FROM transaction_journal j
            INNER JOIN transactions t
                ON t.transaction_id = j.transaction_id
            WHERE t.state IN (
                'PREPARED',
                'WRITING',
                'VERIFYING',
                'COMMITTING'
            )
        """).fetchone()[0]

        terminal_without_marker = conn.execute("""
            SELECT COUNT(*)
            FROM transaction_journal j
            INNER JOIN transactions t
                ON t.transaction_id = j.transaction_id
            WHERE t.state IN (
                'COMMITTED',
                'ROLLBACK'
            )
              AND j.commit_marker = 0
        """).fetchone()[0]

        inconsistent_committed = conn.execute("""
            SELECT COUNT(*)
            FROM transaction_journal j
            INNER JOIN transactions t
                ON t.transaction_id = j.transaction_id
            WHERE t.state = 'COMMITTED'
              AND j.commit_marker = 0
        """).fetchone()[0]

        conn.close()

        if inconsistent_committed:
            status = "ERROR"
        elif pending:
            status = "WARNING"
        else:
            status = "OK"

        return _result(
            status,
            total=total,
            committed_markers=committed_markers,
            verified=verified,
            pending=pending,
            terminal_without_marker=terminal_without_marker,
            inconsistent_committed=inconsistent_committed,
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_integrity():
    try:
        rows = verify_block_ref_counts()

        mismatches = [
            row
            for row in rows
            if row[1] != row[2]
        ]

        if mismatches:
            return {
                "status": "ERROR",
                "detail": "Inconsistência de ref_count detectada.",
                "total_blocks": len(rows),
                "mismatches": mismatches,
            }

        return {
            "status": "OK",
            "total_blocks": len(rows),
            "mismatches": 0,
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "detail": f"{type(exc).__name__}: {exc}",
        }

def check_orphans():
    try:
        orphans = list_unreferenced_blocks()

        return _result(
            "WARNING" if orphans else "OK",
            total=len(orphans),
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def check_capacity():
    try:
        data = allocation_capacity()
        state = data["policy_state"]

        if state == "READ_ONLY":
            status = "CRITICAL"
        elif state == "CRITICAL":
            status = "WARNING"
        else:
            status = "OK"

        return _result(
            status,
            state=state,
            usable_free_bytes=data["usable_free_bytes"],
            device_free_bytes=data["device_free_bytes"],
        )

    except Exception as exc:
        return _result(
            "ERROR",
            f"{type(exc).__name__}: {exc}"
        )


def run_health():
    checks = {
        "identity": check_identity(),
        "registry": check_registry(),
        "namespaces": check_namespaces(),
        "objects": check_objects(),
        "blocks": check_blocks(),
        "manifests": check_manifests(),
        "transactions": check_transactions(),
        "journal": check_journal(),
        "integrity": check_integrity(),
        "orphans": check_orphans(),
        "capacity": check_capacity(),
    }

    errors = sum(
        1
        for result in checks.values()
        if result["status"] in {"ERROR", "CRITICAL"}
    )

    warnings = sum(
        1
        for result in checks.values()
        if result["status"] == "WARNING"
    )

    if errors:
        overall = "CRITICAL"
    elif warnings:
        overall = "WARNING"
    else:
        overall = "HEALTHY"

    return {
        "status": overall,
        "checks": checks,
    }
