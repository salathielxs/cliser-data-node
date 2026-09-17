import node.object_manager as om

from node.registry import (
    get_transaction,
    get_object,
    get_manifest,
    get_block,
    connect,
)

DATA = b"CLISER-REAL-PUT-ROLLBACK-TEST-2026-UNIQUE"


def failing_reconstruct(object_id):
    raise RuntimeError("FALHA CONTROLADA NO VERIFY DO PUT")


def main():

    print("=== REAL PUT ROLLBACK TEST ===")

    # Guarda a função original.
    original_reconstruct = om.reconstruct_object

    # Injeta falha controlada na etapa VERIFYING.
    om.reconstruct_object = failing_reconstruct

    try:

        try:
            om.put_object(
                DATA,
                namespace="default",
            )

            print("ERRO: put_object deveria ter falhado.")

            return 1

        except RuntimeError as exc:
            print("FALHA CAPTURADA:", exc)

    finally:
        # Restaura imediatamente a função original.
        om.reconstruct_object = original_reconstruct

    # ---------------------------------------------------------
    # Descobrir o object_id esperado
    # ---------------------------------------------------------

    import hashlib

    object_id = hashlib.sha256(DATA).hexdigest()

    print()
    print("OBJECT ID:", object_id)

    # ---------------------------------------------------------
    # Procurar transação relacionada
    # ---------------------------------------------------------

    conn = connect()

    tx = conn.execute(
        """
        SELECT
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            error
        FROM transactions
        WHERE object_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (object_id,),
    ).fetchone()

    conn.close()

    print()
    print("TRANSACTION:")
    print(tx)

    # ---------------------------------------------------------
    # Registry
    # ---------------------------------------------------------

    obj = get_object(object_id)
    manifest = get_manifest(object_id)

    print()
    print("OBJECT:")
    print(obj)

    print()
    print("MANIFEST:")
    print(manifest)

    # ---------------------------------------------------------
    # Descobrir blocos eventualmente restantes
    # ---------------------------------------------------------

    conn = connect()

    block_rows = conn.execute(
        """
        SELECT
            mb.block_id,
            b.ref_count,
            b.status,
            b.storage_path
        FROM manifest_blocks mb
        LEFT JOIN blocks b
            ON b.block_id = mb.block_id
        WHERE mb.object_id = ?
        """,
        (object_id,),
    ).fetchall()

    conn.close()

    print()
    print("MANIFEST BLOCKS:")
    print(block_rows)

    # ---------------------------------------------------------
    # Verificação final
    # ---------------------------------------------------------

    transaction_ok = (
        tx is not None
        and tx[4] == "ROLLBACK"
    )

    object_ok = obj is None

    manifest_ok = manifest is None

    blocks_ok = len(block_rows) == 0

    print()
    print("=== VALIDATION ===")
    print("Transaction ROLLBACK:", transaction_ok)
    print("Object removed:", object_ok)
    print("Manifest removed:", manifest_ok)
    print("Manifest blocks removed:", blocks_ok)

    if (
        transaction_ok
        and object_ok
        and manifest_ok
        and blocks_ok
    ):
        print()
        print("REAL PUT ROLLBACK: OK")
        return 0

    print()
    print("REAL PUT ROLLBACK: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
