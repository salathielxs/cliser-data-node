from node.registry import (
    connect,
    list_transactions,
    get_transaction,
    get_transaction_journal,
    update_transaction_state,
    purge_manifest,
    purge_object_record,
    rebuild_block_ref_counts,
    mark_block_deleted,
    remove_block_record,
)


RECOVERABLE_STATES = {
    "PREPARED",
    "WRITING",
    "VERIFYING",
    "COMMITTING",
}


def _block_ids_for_object(object_id):
    if not object_id:
        return []

    conn = connect()

    rows = conn.execute(
        """
        SELECT block_id
        FROM manifest_blocks
        WHERE object_id = ?
        ORDER BY block_index
        """,
        (object_id,),
    ).fetchall()

    conn.close()

    return [row[0] for row in rows]


def _cleanup_orphan_blocks(block_ids):
    if not block_ids:
        return

    rebuild_block_ref_counts()

    conn = connect()

    rows = []

    for block_id in block_ids:
        row = conn.execute(
            """
            SELECT block_id, storage_path, ref_count
            FROM blocks
            WHERE block_id = ?
            """,
            (block_id,),
        ).fetchone()

        if row:
            rows.append(row)

    conn.close()

    for block_id, storage_path, ref_count in rows:
        if ref_count != 0:
            continue

        try:
            mark_block_deleted(block_id)

            from pathlib import Path

            path = Path(storage_path)

            if path.exists():
                path.unlink()

            remove_block_record(block_id)

        except Exception:
            # Não interromper a recuperação dos demais recursos.
            pass


def _verify_direct_object(object_id):
    """
    Verifica objeto armazenado diretamente.
    Retorna True somente se registro, arquivo, tamanho e hash
    estiverem consistentes.
    """
    if not object_id:
        return False

    from pathlib import Path
    import hashlib

    conn = connect()

    row = conn.execute(
        """
        SELECT
            object_id,
            content_hash,
            size,
            storage_path,
            status
        FROM objects
        WHERE object_id = ?
        """,
        (object_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return False

    _, content_hash, size, storage_path, status = row

    if status != "ACTIVE":
        return False

    if not storage_path:
        return False

    path = Path(storage_path)

    if not path.exists():
        return False

    try:
        data = path.read_bytes()
    except Exception:
        return False

    if len(data) != size:
        return False

    calculated = hashlib.sha256(data).hexdigest()

    return calculated == content_hash


def _verify_block_object(object_id):
    """
    Reconstrói e verifica um objeto baseado em manifest/blocos.

    object_id identifica a referência lógica.
    content_hash identifica o conteúdo.
    """
    if not object_id:
        return False

    try:
        from node.manifest import reconstruct_object
        from node.registry import get_object

        data = reconstruct_object(object_id)

        obj = get_object(object_id)

        if obj is None:
            return False

        if obj["status"] != "ACTIVE":
            return False

        calculated = __import__("hashlib").sha256(data).hexdigest()

        return calculated == obj["content_hash"]

    except Exception:
        return False


def _recover_commit(transaction_id, transaction):
    """
    Recupera uma transação cujo Journal possui COMMIT_MARKER=1.

    Regra:
    o marker é uma evidência de que os recursos passaram pela
    verificação e chegaram ao ponto de commit.

    Antes de promover a transação para COMMITTED, os recursos
    precisam continuar fisicamente consistentes.
    """
    object_id = transaction.get("object_id")

    journal = get_transaction_journal(transaction_id)

    if journal is None:
        return {
            "transaction_id": transaction_id,
            "action": "ROLLBACK",
            "reason": "JOURNAL_MISSING",
        }

    resources = journal.get("resources") or {}

    block_mode = resources.get("block_mode", False)

    if block_mode:
        valid = _verify_block_object(object_id)
    else:
        valid = _verify_direct_object(object_id)

    if not valid:
        return {
            "transaction_id": transaction_id,
            "action": "ROLLBACK",
            "reason": "COMMIT_MARKER_BUT_RESOURCES_INVALID",
        }

    update_transaction_state(
        transaction_id,
        "COMMITTED",
    )

    return {
        "transaction_id": transaction_id,
        "action": "COMMIT",
        "reason": "COMMIT_MARKER_VALIDATED",
    }


def _rollback_transaction(transaction_id, transaction):
    object_id = transaction.get("object_id")

    block_ids = _block_ids_for_object(object_id)

    try:
        purge_manifest(object_id)
    except Exception:
        pass

    try:
        purge_object_record(object_id)
    except Exception:
        pass

    _cleanup_orphan_blocks(block_ids)

    update_transaction_state(
        transaction_id,
        "ROLLBACK",
    )

    return {
        "transaction_id": transaction_id,
        "action": "ROLLBACK",
        "reason": "RECOVERABLE_TRANSACTION",
    }


def recover_transaction(transaction_id):
    """
    Recupera uma transação persistida através do Recovery Engine.

    Contrato estável:

        transaction_id
        previous_state
        final_state
        action
        recovered
        commit_marker

    Ações:

        COMMIT
        ROLLBACK
        NOOP
        NOT_FOUND
        NOOP_UNSUPPORTED_STATE

    A recuperação permanece idempotente.
    """

    transaction = get_transaction(transaction_id)

    if transaction is None:
        return {
            "transaction_id": transaction_id,
            "previous_state": None,
            "final_state": None,
            "action": "NOT_FOUND",
            "recovered": False,
            "commit_marker": False,
        }

    previous_state = transaction["state"]

    if previous_state in {"COMMITTED", "ROLLBACK"}:
        return {
            "transaction_id": transaction_id,
            "previous_state": previous_state,
            "final_state": previous_state,
            "action": "NOOP",
            "reason": f"STATE_{previous_state}",
            "recovered": False,
            "commit_marker": False,
        }

    if previous_state not in RECOVERABLE_STATES:
        return {
            "transaction_id": transaction_id,
            "previous_state": previous_state,
            "final_state": previous_state,
            "action": "NOOP_UNSUPPORTED_STATE",
            "state": previous_state,
            "recovered": False,
            "commit_marker": False,
        }

    journal = get_transaction_journal(transaction_id)

    commit_marker = bool(
        journal.get("commit_marker", False)
    ) if journal is not None else False

    # Sem Journal, não existe evidência suficiente para completar commit.
    if journal is None:
        result = _rollback_transaction(
            transaction_id,
            transaction,
        )

        return {
            **result,
            "previous_state": previous_state,
            "final_state": "ROLLBACK",
            "recovered": True,
            "commit_marker": False,
        }

    # Marker ausente = operação não chegou ao commit.
    if not commit_marker:
        result = _rollback_transaction(
            transaction_id,
            transaction,
        )

        return {
            **result,
            "previous_state": previous_state,
            "final_state": "ROLLBACK",
            "recovered": True,
            "commit_marker": False,
        }

    # Marker presente = tentar completar commit.
    result = _recover_commit(
        transaction_id,
        transaction,
    )

    if result["action"] == "COMMIT":
        return {
            **result,
            "previous_state": previous_state,
            "final_state": "COMMITTED",
            "recovered": True,
            "commit_marker": True,
        }

    # Marker presente, mas recursos inválidos.
    rollback = _rollback_transaction(
        transaction_id,
        transaction,
    )

    return {
        **rollback,
        "previous_state": previous_state,
        "final_state": "ROLLBACK",
        "recovered": True,
        "commit_marker": True,
    }




def recover_pending_transactions():
    """
    Recupera todas as transações persistidas em estado recuperável.

    Retorna um relatório determinístico:

        total_pending
        processed
        recovered
        noop
        errors
        results

    Apenas transações em RECOVERABLE_STATES são processadas.
    Estados terminais não são incluídos no relatório batch.
    """

    rows = list_transactions()

    results = []
    recovered = 0
    noop = 0
    errors = 0

    pending_rows = [
        row
        for row in rows
        if row[4] in RECOVERABLE_STATES
    ]

    for row in pending_rows:
        transaction_id = row[0]
        previous_state = row[4]

        try:
            result = recover_transaction(
                transaction_id
            )

            result = {
                **result,
                "status": "OK",
            }

            results.append(result)

            if result.get("recovered") is True:
                recovered += 1
            else:
                noop += 1

        except Exception as exc:
            errors += 1

            results.append({
                "transaction_id": transaction_id,
                "previous_state": previous_state,
                "final_state": None,
                "action": "ERROR",
                "recovered": False,
                "commit_marker": False,
                "status": "ERROR",
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            })

    return {
        "total_pending": len(pending_rows),
        "processed": len(results),
        "recovered": recovered,
        "noop": noop,
        "errors": errors,
        "results": results,
    }




def recovery_status():
    transactions = list_transactions()

    states = {}

    for tx in transactions:
        state = tx[4]
        states[state] = states.get(state, 0) + 1

    recoverable = sum(
        states.get(state, 0)
        for state in RECOVERABLE_STATES
    )

    return {
        "total": len(transactions),
        "states": states,
        "recoverable": recoverable,
    }
