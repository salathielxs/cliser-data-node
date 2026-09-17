import sys
import json
import shutil
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node import object_manager
from node import registry
from node import namespace_manager
from node.registry import connect
from node.recovery import recover_pending_transactions


TEST_NS = "atomicity_test"


def banner():
    print("\nCLISER DATA NODE — ATOMICITY TEST")
    print("=" * 50)


def ensure_test_namespace():
    if not namespace_manager.namespace_exists(TEST_NS):
        namespace_manager.create_namespace(
            TEST_NS,
            quota_bytes=0,
        )

    # O sistema diferencia "quota não configurada"
    # de "quota ilimitada". Registramos explicitamente
    # a quota através do registry existente.
    from datetime import datetime, timezone

    registry.register_quota(
        TEST_NS,
        0,
        datetime.now(timezone.utc).isoformat(),
    )


def cleanup_namespace():
    conn = connect()

    rows = conn.execute(
        "SELECT object_id FROM objects WHERE namespace = ?",
        (TEST_NS,),
    ).fetchall()

    object_ids = [r[0] for r in rows]

    conn.execute(
        "DELETE FROM manifest_blocks WHERE object_id IN "
        "(SELECT object_id FROM manifests WHERE namespace = ?)",
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM manifests WHERE namespace = ?",
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM objects WHERE namespace = ?",
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM quotas WHERE namespace = ?",
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM transaction_journal "
        "WHERE transaction_id IN "
        "(SELECT transaction_id FROM transactions WHERE namespace = ?)",
        (TEST_NS,),
    )

    conn.execute(
        "DELETE FROM transactions WHERE namespace = ?",
        (TEST_NS,),
    )

    conn.commit()
    conn.close()

    for object_id in object_ids:
        path = Path(object_manager.OBJECTS_DIR) / object_id
        if path.exists():
            path.unlink()

    ensure_test_namespace()


def snapshot():
    conn = connect()

    objects = conn.execute(
        """
        SELECT object_id, content_hash, size, namespace, status
        FROM objects
        WHERE namespace = ?
        ORDER BY object_id
        """,
        (TEST_NS,),
    ).fetchall()

    manifests = conn.execute(
        """
        SELECT object_id, namespace, total_size,
               block_size, block_count, status
        FROM manifests
        WHERE namespace = ?
        ORDER BY object_id
        """,
        (TEST_NS,),
    ).fetchall()

    blocks = conn.execute(
        """
        SELECT block_id, size, status, ref_count
        FROM blocks
        ORDER BY block_id
        """
    ).fetchall()

    transactions = conn.execute(
        """
        SELECT transaction_id, object_id, namespace,
               operation, state, error
        FROM transactions
        WHERE namespace = ?
        ORDER BY created_at
        """,
        (TEST_NS,),
    ).fetchall()

    journals = conn.execute(
        """
        SELECT tj.transaction_id,
               tj.phase,
               tj.commit_marker,
               tj.verified,
               tj.resources
        FROM transaction_journal tj
        JOIN transactions t
          ON t.transaction_id = tj.transaction_id
        WHERE t.namespace = ?
        ORDER BY tj.transaction_id
        """,
        (TEST_NS,),
    ).fetchall()

    conn.close()

    return {
        "objects": objects,
        "manifests": manifests,
        "blocks": blocks,
        "transactions": transactions,
        "journals": journals,
    }


def inject_failure_after_resources():
    original = registry.update_transaction_journal

    def patched(
        transaction_id,
        phase=None,
        resources=None,
        verified=None,
        commit_marker=None,
    ):
        result = original(
            transaction_id,
            phase=phase,
            resources=resources,
            verified=verified,
            commit_marker=commit_marker,
        )

        if phase == "RESOURCES":
            raise RuntimeError(
                "FALHA INJETADA: after_resources"
            )

        return result

    registry.update_transaction_journal = patched


def restore_registry():
    import importlib
    importlib.reload(registry)


def test_direct_atomicity():
    print("\n[1] DIRECT — falha após escrita")

    cleanup_namespace()

    data = b"CLISER-DIRECT-ATOMICITY-" * 4

    before = snapshot()

    inject_failure_after_resources()

    try:
        object_manager.put_object(
            data,
            namespace=TEST_NS,
        )
        raise AssertionError(
            "A operação deveria falhar."
        )
    except RuntimeError:
        pass
    finally:
        restore_registry()

    after = snapshot()

    if after["objects"] != before["objects"]:
        raise AssertionError(
            "Registry de objetos não foi restaurado."
        )

    if after["manifests"] != before["manifests"]:
        raise AssertionError(
            "Manifestos foram alterados."
        )

    path_files = list(
        Path(object_manager.OBJECTS_DIR).glob("*")
    )

    for path in path_files:
        if path.is_file() and path.stat().st_size == len(data):
            raise AssertionError(
                "Payload DIRECT residual encontrado."
            )

    if not after["transactions"]:
        raise AssertionError(
            "Transação não registrada."
        )

    tx = after["transactions"][-1]

    if tx[4] != "ROLLBACK":
        raise AssertionError(
            f"Estado esperado ROLLBACK, obtido {tx[4]}"
        )

    journal = after["journals"][-1]

    if journal[1] != "ROLLBACK":
        raise AssertionError(
            f"Journal esperado ROLLBACK, obtido {journal[1]}"
        )

    if journal[2] != 0:
        raise AssertionError(
            "Commit marker não pode existir após rollback."
        )

    print("DIRECT ROLLBACK: OK")
    print("DIRECT JOURNAL: OK")
    print("DIRECT REGISTRY: OK")


def test_block_atomicity():
    print("\n[2] BLOCKS — falha após criação do manifesto")

    cleanup_namespace()

    data = bytes(range(256)) * 2

    before = snapshot()

    inject_failure_after_resources()

    try:
        object_manager.put_object(
            data,
            namespace=TEST_NS,
        )
        raise AssertionError(
            "A operação deveria falhar."
        )
    except RuntimeError:
        pass
    finally:
        restore_registry()

    after = snapshot()

    active_objects = [
        row for row in after["objects"]
        if row[3] == TEST_NS and row[4] == "ACTIVE"
    ]

    active_manifests = [
        row for row in after["manifests"]
        if row[1] == TEST_NS and row[5] == "ACTIVE"
    ]

    if active_objects:
        raise AssertionError(
            f"Objeto ACTIVE residual: {active_objects}"
        )

    if active_manifests:
        raise AssertionError(
            f"Manifest ACTIVE residual: {active_manifests}"
        )

    tx = after["transactions"][-1]

    if tx[4] != "ROLLBACK":
        raise AssertionError(
            f"Estado esperado ROLLBACK, obtido {tx[4]}"
        )

    journal = after["journals"][-1]

    if journal[1] != "ROLLBACK":
        raise AssertionError(
            f"Journal esperado ROLLBACK, obtido {journal[1]}"
        )

    print("BLOCK ROLLBACK: OK")
    print("BLOCK REGISTRY: OK")
    print("BLOCK JOURNAL: OK")


def test_shared_block_protection():
    print("\n[3] SHARED BLOCK — proteção contra rollback indevido")

    cleanup_namespace()

    data = b"A" * 32

    first = object_manager.put_object(
        data,
        namespace=TEST_NS,
    )

    first_id = first["object_id"]

    # Captura a relação real do bloco compartilhado antes do rollback.
    conn = connect()

    block_before = conn.execute("""
        SELECT
            b.block_id,
            b.ref_count,
            COUNT(mb.block_id) AS calculated_refs
        FROM blocks b
        JOIN manifest_blocks mb
            ON mb.block_id = b.block_id
        WHERE mb.object_id = ?
        GROUP BY b.block_id
    """, (first_id,)).fetchone()

    conn.close()

    if block_before is None:
        raise AssertionError(
            "Bloco compartilhado não encontrado antes do rollback."
        )

    if block_before[1] != block_before[2]:
        raise AssertionError(
            "ref_count inconsistente antes do rollback: "
            f"registrado={block_before[1]}, "
            f"real={block_before[2]}"
        )

    before = snapshot()

    inject_failure_after_resources()

    try:
        object_manager.put_object(
            data,
            namespace=TEST_NS,
        )
        raise AssertionError(
            "A segunda operação deveria falhar."
        )
    except RuntimeError:
        pass
    finally:
        restore_registry()

    after = snapshot()

    obj = registry.get_object(first_id)

    if obj is None:
        raise AssertionError(
            "Objeto original foi removido."
        )

    if obj["status"] != "ACTIVE":
        raise AssertionError(
            "Objeto original deixou de estar ACTIVE."
        )

    if after["objects"] != before["objects"]:
        raise AssertionError(
            "Rollback alterou objetos existentes."
        )

    # Revalida a invariável do bloco compartilhado após o rollback.
    conn = connect()

    block_after = conn.execute("""
        SELECT
            b.block_id,
            b.ref_count,
            COUNT(mb.block_id) AS calculated_refs
        FROM blocks b
        JOIN manifest_blocks mb
            ON mb.block_id = b.block_id
        WHERE mb.object_id = ?
        GROUP BY b.block_id
    """, (first_id,)).fetchone()

    conn.close()

    if block_after is None:
        raise AssertionError(
            "Bloco compartilhado desapareceu após o rollback."
        )

    if block_after[1] != block_after[2]:
        raise AssertionError(
            "ROLLBACK deixou ref_count inconsistente: "
            f"registrado={block_after[1]}, "
            f"real={block_after[2]}"
        )

    if block_after[0] != block_before[0]:
        raise AssertionError(
            "O bloco compartilhado foi alterado durante o rollback."
        )

    print("SHARED OBJECT PRESERVED: OK")
    print("SHARED REGISTRY: OK")
    print("SHARED REFCOUNT BEFORE: OK")
    print("SHARED REFCOUNT AFTER: OK")


def test_recovery_idempotency():
    print("\n[4] RECOVERY — idempotência")

    cleanup_namespace()

    transaction_id = "atomicity-recovery-test"

    try:
        registry.create_transaction(
            transaction_id=transaction_id,
            object_id="recovery-object",
            namespace=TEST_NS,
            operation="PUT",
            state="PREPARED",
            metadata={"test": True},
        )

        registry.create_transaction_journal(
            transaction_id=transaction_id,
            phase="INTENT",
            resources={
                "object_id": "recovery-object",
                "namespace": TEST_NS,
            },
        )

        result1 = recover_pending_transactions()

        result2 = recover_pending_transactions()

        if result1.get("errors", 0) != 0:
            raise AssertionError(
                f"Primeiro recovery apresentou erros: {result1}"
            )

        if result2.get("errors", 0) != 0:
            raise AssertionError(
                f"Segundo recovery apresentou erros: {result2}"
            )

        tx = registry.get_transaction(transaction_id)

        if tx is None:
            raise AssertionError(
                "Transação de recovery desapareceu."
            )

        if tx["state"] != "ROLLBACK":
            raise AssertionError(
                f"Estado esperado ROLLBACK, obtido {tx['state']}"
            )

        print("RECOVERY FIRST RUN: OK")
        print("RECOVERY SECOND RUN: OK")
        print("RECOVERY IDEMPOTENCY: OK")

    finally:
        cleanup_namespace()


def main():
    banner()

    try:
        test_direct_atomicity()
        test_block_atomicity()
        test_shared_block_protection()
        test_recovery_idempotency()

        cleanup_namespace()

        print("\n" + "=" * 50)
        print("ATOMICITY: PASS")
        print("FASE 12 — VALIDAÇÃO INICIAL CONCLUÍDA")
        print("=" * 50)

    except Exception as exc:
        print("\n" + "=" * 50)
        print("ATOMICITY: FAIL")
        print("=" * 50)
        print(f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
