import hashlib
import uuid
from pathlib import Path

import node.object_manager as object_manager
import node.registry as registry

from node.object_manager import put_object
from node.recovery import recover_transaction


class SimulatedCrash(BaseException):
    pass


def count_rows(table):
    conn = registry.connect()
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()
    conn.close()
    return row[0]


def get_transaction_by_object(object_id):
    transactions = registry.list_transactions()

    for tx in transactions:
        if tx[1] == object_id:
            return registry.get_transaction(tx[0])

    return None


def get_block(block_id):
    conn = registry.connect()

    row = conn.execute(
        """
        SELECT
            block_id,
            content_hash,
            size,
            storage_path,
            status,
            ref_count
        FROM blocks
        WHERE block_id = ?
        """,
        (block_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "block_id": row[0],
        "content_hash": row[1],
        "size": row[2],
        "storage_path": row[3],
        "status": row[4],
        "ref_count": row[5],
    }


def get_journal(transaction_id):
    return registry.get_transaction_journal(transaction_id)


def assert_object_removed(object_id):
    conn = registry.connect()

    object_row = conn.execute(
        """
        SELECT object_id
        FROM objects
        WHERE object_id = ?
        """,
        (object_id,),
    ).fetchone()

    manifest_row = conn.execute(
        """
        SELECT object_id
        FROM manifests
        WHERE object_id = ?
        """,
        (object_id,),
    ).fetchone()

    manifest_blocks = conn.execute(
        """
        SELECT COUNT(*)
        FROM manifest_blocks
        WHERE object_id = ?
        """,
        (object_id,),
    ).fetchone()[0]

    conn.close()

    assert object_row is None, (
        f"Objeto ainda existe: {object_id}"
    )

    assert manifest_row is None, (
        f"Manifest ainda existe: {object_id}"
    )

    assert manifest_blocks == 0, (
        f"Manifest blocks ainda existem: {manifest_blocks}"
    )


def install_journal_crash(target_phase):
    original_create = registry.create_transaction_journal
    original_update = registry.update_transaction_journal

    def crash_after_create(
        transaction_id,
        phase,
        resources=None,
        verified=False,
    ):
        result = original_create(
            transaction_id,
            phase,
            resources,
            verified,
        )

        if phase == target_phase:
            raise SimulatedCrash(
                f"CRASH APÓS {target_phase}"
            )

        return result

    def crash_after_update(
        transaction_id,
        phase=None,
        resources=None,
        verified=None,
        commit_marker=None,
    ):
        result = original_update(
            transaction_id,
            phase,
            resources,
            verified,
            commit_marker,
        )

        if phase == target_phase:
            raise SimulatedCrash(
                f"CRASH APÓS {target_phase}"
            )

        return result

    registry.create_transaction_journal = crash_after_create
    registry.update_transaction_journal = crash_after_update

    return original_create, original_update


def install_state_crash(target_state):
    original = registry.update_transaction_state

    def crash_after_state(
        transaction_id,
        state,
        error=None,
    ):
        result = original(
            transaction_id,
            state,
            error,
        )

        if state == target_state:
            raise SimulatedCrash(
                f"CRASH APÓS {target_state}"
            )

        return result

    registry.update_transaction_state = crash_after_state

    return original


def restore_journal(original_create, original_update):
    registry.create_transaction_journal = original_create
    registry.update_transaction_journal = original_update


def restore_state(original):
    registry.update_transaction_state = original


def run_crash_before_commit(label, phase):
    print("=" * 60)
    print(f"TESTE: CRASH APÓS {label}")
    print("=" * 60)

    data = (
        f"CLISER-CRASH-{label}-{uuid.uuid4().hex}"
    ).encode()

    # O object_id atual do runtime é UUID aleatório.
    # Portanto, não pode ser derivado por SHA-256(data).
    # O SHA-256 é content_hash, não object_id.
    before_transactions = {
        row[0]
        for row in registry.list_transactions()
    }

    original_create, original_update = install_journal_crash(
        phase
    )

    try:
        try:
            put_object(
                data,
                namespace="default",
            )

            raise AssertionError(
                f"Crash esperado após {phase} não ocorreu."
            )

        except SimulatedCrash:
            pass

    finally:
        restore_journal(
            original_create,
            original_update,
        )

    after_transactions = registry.list_transactions()

    new_transactions = [
        row
        for row in after_transactions
        if row[0] not in before_transactions
    ]

    assert len(new_transactions) == 1, (
        f"Quantidade inesperada de transações novas: "
        f"{len(new_transactions)}"
    )

    transaction = registry.get_transaction(
        new_transactions[0][0]
    )

    assert transaction is not None, (
        "Transação não encontrada após crash."
    )

    object_id = transaction["object_id"]

    assert transaction["state"] in {
        "PREPARED",
        "WRITING",
        "VERIFYING",
        "COMMITTING",
    }, (
        f"Estado inesperado: {transaction['state']}"
    )

    journal = get_journal(
        transaction["transaction_id"]
    )

    assert journal is not None, (
        "Journal não encontrado."
    )

    assert journal["commit_marker"] is False, (
        "Commit marker não deveria estar ativo."
    )

    result = recover_transaction(
        transaction["transaction_id"]
    )

    assert result["action"] == "ROLLBACK", result

    recovered = registry.get_transaction(
        transaction["transaction_id"]
    )

    assert recovered["state"] == "ROLLBACK", (
        recovered
    )

    assert_object_removed(object_id)

    print(
        f"TRANSAÇÃO: {transaction['transaction_id']}"
    )

    print(
        f"ESTADO ANTES: {transaction['state']}"
    )

    print(
        f"RECOVERY: {result['action']}"
    )

    print(
        f"ESTADO FINAL: {recovered['state']}"
    )

    print(
        f"OBJETO REMOVIDO: {object_id}"
    )

    print(f"CRASH APÓS {label}: OK")
    print()


def run_crash_after_commit_marker():
    print("=" * 60)
    print("TESTE: CRASH APÓS COMMIT_MARKER")
    print("=" * 60)

    data = (
        f"CLISER-COMMIT-MARKER-{uuid.uuid4().hex}"
    ).encode()

    before_transactions = {
        row[0]
        for row in registry.list_transactions()
    }

    original_create, original_update = install_journal_crash(
        "COMMIT_MARKER"
    )

    try:
        try:
            put_object(
                data,
                namespace="default",
            )

            raise AssertionError(
                "Crash esperado após COMMIT_MARKER não ocorreu."
            )

        except SimulatedCrash:
            pass

    finally:
        restore_journal(
            original_create,
            original_update,
        )

    after_transactions = registry.list_transactions()

    new_transactions = [
        row
        for row in after_transactions
        if row[0] not in before_transactions
    ]

    assert len(new_transactions) == 1, (
        f"Quantidade inesperada de transações novas: "
        f"{len(new_transactions)}"
    )

    transaction = registry.get_transaction(
        new_transactions[0][0]
    )

    assert transaction is not None

    object_id = transaction["object_id"]

    assert transaction["state"] == "COMMITTING", (
        transaction
    )

    journal = get_journal(
        transaction["transaction_id"]
    )

    assert journal is not None

    assert journal["phase"] == "COMMIT_MARKER"

    assert journal["commit_marker"] is True

    assert journal["verified"] is True

    result = recover_transaction(
        transaction["transaction_id"]
    )

    assert result["action"] == "COMMIT", result

    recovered = registry.get_transaction(
        transaction["transaction_id"]
    )

    assert recovered["state"] == "COMMITTED"

    print(
        f"TRANSAÇÃO: {transaction['transaction_id']}"
    )

    print("ESTADO ANTES: COMMITTING")
    print("JOURNAL: COMMIT_MARKER")
    print("COMMIT MARKER: True")
    print("RECOVERY: COMMIT")
    print("ESTADO FINAL: COMMITTED")

    print("CRASH APÓS COMMIT_MARKER: OK")
    print()


def run_crash_after_committed():
    print("=" * 60)
    print("TESTE: CRASH APÓS COMMITTED")
    print("=" * 60)

    data = (
        f"CLISER-COMMITTED-{uuid.uuid4().hex}"
    ).encode()

    before_transactions = {
        row[0]
        for row in registry.list_transactions()
    }

    original = install_state_crash(
        "COMMITTED"
    )

    try:
        try:
            put_object(
                data,
                namespace="default",
            )

            raise AssertionError(
                "Crash esperado após COMMITTED não ocorreu."
            )

        except SimulatedCrash:
            pass

    finally:
        restore_state(original)

    after_transactions = registry.list_transactions()

    new_transactions = [
        row
        for row in after_transactions
        if row[0] not in before_transactions
    ]

    assert len(new_transactions) == 1, (
        f"Quantidade inesperada de transações novas: "
        f"{len(new_transactions)}"
    )

    transaction = registry.get_transaction(
        new_transactions[0][0]
    )

    assert transaction is not None

    assert transaction["state"] == "COMMITTED"

    result = recover_transaction(
        transaction["transaction_id"]
    )

    assert result["action"] == "NOOP"

    assert result["reason"] == "STATE_COMMITTED"

    recovered = registry.get_transaction(
        transaction["transaction_id"]
    )

    assert recovered["state"] == "COMMITTED"

    print(
        f"TRANSAÇÃO: {transaction['transaction_id']}"
    )

    print("ESTADO: COMMITTED")
    print("RECOVERY: NOOP")
    print("DADOS PRESERVADOS: SIM")

    print("CRASH APÓS COMMITTED: OK")
    print()


def main():
    print()
    print("#" * 60)
    print("# CLISER DATA NODE")
    print("# CRASH / RECOVERY AUTOMATED TEST")
    print("#" * 60)
    print()

    initial_objects = count_rows("objects")
    initial_transactions = count_rows("transactions")

    print(
        f"OBJETOS INICIAIS: {initial_objects}"
    )

    print(
        f"TRANSAÇÕES INICIAIS: {initial_transactions}"
    )

    print()

    run_crash_before_commit(
        "INTENT",
        "INTENT",
    )

    run_crash_before_commit(
        "RESOURCES",
        "RESOURCES",
    )

    run_crash_before_commit(
        "VERIFIED",
        "VERIFIED",
    )

    run_crash_after_commit_marker()

    run_crash_after_committed()

    final_objects = count_rows("objects")
    final_transactions = count_rows("transactions")

    print("=" * 60)
    print("VALIDAÇÃO FINAL")
    print("=" * 60)

    print(
        f"OBJETOS INICIAIS   : {initial_objects}"
    )

    print(
        f"OBJETOS FINAIS     : {final_objects}"
    )

    print(
        f"TRANSAÇÕES INICIAIS: {initial_transactions}"
    )

    print(
        f"TRANSAÇÕES FINAIS  : {final_transactions}"
    )

    expected_objects = initial_objects + 2
    expected_transactions = initial_transactions + 5

    assert final_objects == expected_objects, (
        f"Quantidade de objetos inesperada: "
        f"{final_objects} != {expected_objects}"
    )

    assert final_transactions == expected_transactions, (
        f"Quantidade de transações inesperada: "
        f"{final_transactions} != {expected_transactions}"
    )

    print()
    print("=" * 60)
    print("CRASH / RECOVERY AUTOMATED TEST: OK")
    print("=" * 60)
    print()



if __name__ == "__main__":
    main()
