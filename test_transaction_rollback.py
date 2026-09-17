import uuid
from pathlib import Path

from node.transaction import Transaction, TransactionState
from node.block_manager import store_block
from node.registry import (
    connect,
    create_transaction,
    get_transaction,
    update_transaction_state,
    get_object,
    get_block,
    mark_block_deleted,
    remove_block_record,
    rebuild_block_ref_counts,
)

DATA = b"CLISER-ROLLBACK-TEST-DATA"


def main():
    transaction_id = uuid.uuid4().hex
    block_id = None

    print("TRANSACTION:", transaction_id)

    # ---------------------------------------------------------
    # PREPARED
    # ---------------------------------------------------------

    tx = Transaction(transaction_id)

    create_transaction(
        transaction_id=transaction_id,
        operation="PUT",
        state=tx.state.value,
        object_id=None,
        namespace="default",
    )

    print("STATE:", tx.state.value)

    # ---------------------------------------------------------
    # WRITING
    # ---------------------------------------------------------

    tx.transition(TransactionState.WRITING)

    update_transaction_state(
        transaction_id,
        tx.state.value,
    )

    print("STATE:", tx.state.value)

    # ---------------------------------------------------------
    # CRIA BLOCO
    # ---------------------------------------------------------

    block = store_block(DATA)
    block_id = block["block_id"]

    print("BLOCK CREATED:", block_id)

    conn = connect()

    row = conn.execute(
        """
        SELECT
            block_id,
            ref_count,
            status,
            storage_path
        FROM blocks
        WHERE block_id = ?
        """,
        (block_id,),
    ).fetchone()

    conn.close()

    print("BLOCK BEFORE FAILURE:", row)

    # ---------------------------------------------------------
    # FALHA CONTROLADA
    # ---------------------------------------------------------

    error_message = "FALHA CONTROLADA PARA TESTE DE ROLLBACK"

    tx.fail(error_message)

    update_transaction_state(
        transaction_id,
        tx.state.value,
        error=error_message,
    )

    print("STATE:", tx.state.value)
    print("ERROR:", error_message)

    # ---------------------------------------------------------
    # ROLLBACK
    # ---------------------------------------------------------

    try:
        rebuild_block_ref_counts()
    except Exception:
        pass

    if block_id:

        conn = connect()

        row = conn.execute(
            """
            SELECT
                block_id,
                ref_count,
                status,
                storage_path
            FROM blocks
            WHERE block_id = ?
            """,
            (block_id,),
        ).fetchone()

        conn.close()

        if row is not None and row[1] == 0:

            block_path = Path(row[3])

            # Primeiro altera o estado lógico.
            mark_block_deleted(block_id)

            # Depois remove o payload físico.
            if block_path.exists():
                block_path.unlink()

            # Finalmente remove o registro.
            remove_block_record(block_id)

            print("BLOCK ROLLBACK: REMOVED")

    tx.rollback()

    update_transaction_state(
        transaction_id,
        tx.state.value,
    )

    print("STATE:", tx.state.value)

    # ---------------------------------------------------------
    # VALIDATION
    # ---------------------------------------------------------

    print()
    print("=== VALIDATION ===")

    transaction = get_transaction(transaction_id)
    obj = get_object(block_id)
    block_after = get_block(block_id)

    print("Transaction:")
    print(transaction)

    print()
    print("Object:")
    print(obj)

    print()
    print("Block:")
    print(block_after)

    valid = (
        transaction is not None
        and transaction["state"] == "ROLLBACK"
        and obj is None
        and block_after is None
    )

    if valid:
        print()
        print("ROLLBACK TEST: OK")
        return 0

    print()
    print("ROLLBACK TEST: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
