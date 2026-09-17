import hashlib
from pathlib import Path

from node.storage import OBJECTS_DIR
from node.registry import (
    list_unreferenced_blocks,    rebuild_block_ref_counts,    connect,
    get_namespace,
    get_object,
    get_manifest,
    register_object,
    delete_object,
    all_objects,
    reconcile_object,
    remove_object_record,
    delete_manifest,
    purge_manifest,
    purge_object_record,
    delete_unreferenced_blocks,
    mark_block_deleted,
    remove_block_record,
    create_idempotent_transaction,
    update_transaction_metadata,
)
from node.manifest import create_manifest, reconstruct_object
from node.capacity import can_allocate
from node.quota import can_allocate_quota
from node.allocation import estimate_allocation


BLOCK_THRESHOLD = 16


class IdempotencyConflictError(Exception):
    pass


class IdempotencyInProgressError(Exception):
    pass


class IdempotencyReplayError(Exception):
    pass


def put_object(
    data: bytes,
    namespace="default",
    quota_mode="LOGICAL",
    idempotency_key=None,
    request_fingerprint=None,
):
    import uuid

    if not isinstance(data, bytes):
        raise TypeError("data deve ser bytes.")

    if not namespace:
        raise ValueError("namespace inválido.")

    if idempotency_key is not None:
        if not isinstance(idempotency_key, str):
            raise ValueError(
                "idempotency_key deve ser texto."
            )

        idempotency_key = idempotency_key.strip()

        if not idempotency_key:
            raise ValueError(
                "idempotency_key não pode ser vazio."
            )

    quota_mode = quota_mode.upper()

    if quota_mode not in {"LOGICAL", "PHYSICAL", "HYBRID"}:
        raise ValueError(
            "quota_mode inválido. "
            "Use LOGICAL, PHYSICAL ou HYBRID."
        )

    # ---------------------------------------------------------
    # 0. VALIDAR NAMESPACE
    # ---------------------------------------------------------

    namespace_info = get_namespace(namespace)

    if namespace_info is None:
        raise ValueError(
            f"Namespace não encontrado: {namespace}"
        )

    if namespace_info["status"] != "ACTIVE":
        raise PermissionError(
            f"Namespace não está ACTIVE: {namespace}"
        )

    required_bytes = len(data)

    content_hash = hashlib.sha256(data).hexdigest()

    # object_id = identidade lógica da referência.
    # content_hash = identidade do conteúdo.
    object_id = uuid.uuid4().hex

    block_mode = len(data) > BLOCK_THRESHOLD

    # ---------------------------------------------------------
    # 1. PLANO DE ALOCAÇÃO
    # ---------------------------------------------------------

    allocation = estimate_allocation(
        data,
        block_mode=block_mode,
        namespace=namespace,
    )

    physical_delta = allocation["physical_payload_delta"]

    # ---------------------------------------------------------
    # 2. QUOTA
    # ---------------------------------------------------------

    if quota_mode == "LOGICAL":
        quota_required = required_bytes

    elif quota_mode == "PHYSICAL":
        quota_required = physical_delta

    else:
        quota_required = max(
            required_bytes,
            physical_delta,
        )

    quota = can_allocate_quota(
        quota_required,
        namespace=namespace,
        mode=quota_mode,
    )

    if not quota["allowed"]:
        raise OSError(
            f"Quota denied: {quota['reason']}"
        )

    # ---------------------------------------------------------
    # 3. CAPACIDADE FÍSICA
    # ---------------------------------------------------------

    capacity = can_allocate(
        physical_delta
    )

    if not capacity["allowed"]:
        raise OSError(
            f"Storage capacity denied: {capacity['reason']}"
        )

    # ---------------------------------------------------------
    # 4. CRIAR TRANSAÇÃO
    # ---------------------------------------------------------

    transaction_id = uuid.uuid4().hex

    from node.transaction import (
        Transaction,
        TransactionState,
    )

    from node.registry import (
        create_transaction,
        update_transaction_state,
        create_transaction_journal,
        update_transaction_journal,
    )

    tx = Transaction(transaction_id)

    transaction_metadata = {
        "size": required_bytes,
        "block_mode": block_mode,
        "block_size": allocation.get(
            "block_size",
            None,
        ),
        "physical_delta": physical_delta,
        "quota_mode": quota_mode,
    }

    # ---------------------------------------------------------
    # 4.1 IDEMPOTENCY RESERVATION
    # ---------------------------------------------------------
    #
    # A reserva é feita antes de qualquer escrita física.
    # O índice UNIQUE do SQLite garante atomicidade contra
    # requisições concorrentes usando a mesma chave.

    if idempotency_key is not None:
        reservation = create_idempotent_transaction(
            transaction_id=transaction_id,
            object_id=object_id,
            namespace=namespace,
            operation="PUT",
            state=tx.state.value,
            metadata=transaction_metadata,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
        )

        if not reservation["created"]:
            existing = reservation["transaction"]

            existing_fingerprint = (
                existing.get("request_fingerprint")
            )

            if (
                existing_fingerprint is not None
                and existing_fingerprint != request_fingerprint
            ):
                raise IdempotencyConflictError(
                    "Idempotency-Key já foi utilizada "
                    "com uma requisição diferente."
                )

            existing_state = existing["state"]

            if existing_state == "COMMITTED":
                metadata = existing.get("metadata") or {}
                replay_result = metadata.get(
                    "idempotency_response"
                )

                if replay_result is None:
                    raise IdempotencyReplayError(
                        "Transação idempotente COMMITTED "
                        "sem resposta persistida."
                    )

                return replay_result

            if existing_state in {
                "PREPARED",
                "WRITING",
                "VERIFYING",
                "COMMITTING",
            }:
                raise IdempotencyInProgressError(
                    "Já existe uma transação em andamento "
                    "para esta Idempotency-Key."
                )

            raise IdempotencyReplayError(
                "Idempotency-Key já está associada "
                "a uma transação encerrada sem sucesso."
            )

    else:
        create_transaction(
            transaction_id=transaction_id,
            object_id=object_id,
            namespace=namespace,
            operation="PUT",
            state=tx.state.value,
            metadata=transaction_metadata,
        )

    create_transaction_journal(
        transaction_id=transaction_id,
        phase="INTENT",
        resources={
            "object_id": object_id,
            "namespace": namespace,
            "operation": "PUT",
            "block_mode": block_mode,
        },
    )

    created_direct_file = None
    created_block_ids = []
    manifest_created = False
    object_registered = False

    try:
        # -----------------------------------------------------
        # 5. WRITING
        # -----------------------------------------------------

        tx.transition(TransactionState.WRITING)

        update_transaction_state(
            transaction_id,
            tx.state.value,
        )

        # -----------------------------------------------------
        # 6. DIRECT OBJECT
        # -----------------------------------------------------

        if not block_mode:
            OBJECTS_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            object_path = OBJECTS_DIR / object_id

            if not object_path.exists():
                object_path.write_bytes(data)
                created_direct_file = object_path

            # Verificação física antes do registry.
            written_data = object_path.read_bytes()

            if len(written_data) != len(data):
                raise ValueError(
                    "Tamanho do objeto escrito diferente do esperado."
                )

            written_hash = hashlib.sha256(
                written_data
            ).hexdigest()

            if written_hash != content_hash:
                raise ValueError(
                    "Hash do objeto escrito diferente do esperado."
                )

        # -----------------------------------------------------
        # 7. BLOCK OBJECT
        # -----------------------------------------------------

        else:
            # Descobrir quais blocos eram novos antes da criação.
            conn = connect()

            existing_block_ids = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT block_id
                    FROM blocks
                    WHERE status = 'ACTIVE'
                    """
                ).fetchall()
            }

            conn.close()

            planned_new_blocks = {
                block["block_id"]
                for block in allocation["blocks"]
                if block["block_id"] not in existing_block_ids
            }

            manifest = create_manifest(
                data,
                namespace=namespace,
                object_id=object_id,
            )

            manifest_created = True

            created_block_ids = list(
                planned_new_blocks
            )

        # -----------------------------------------------------
        # JOURNAL: RESOURCES
        # -----------------------------------------------------

        journal_resources = {
            "object_id": object_id,
            "namespace": namespace,
            "block_mode": block_mode,
            "created_direct_file": (
                str(created_direct_file)
                if created_direct_file is not None
                else None
            ),
            "created_block_ids": created_block_ids,
            "manifest_created": manifest_created,
            "object_registered": object_registered,
        }

        update_transaction_journal(
            transaction_id,
            phase="RESOURCES",
            resources=journal_resources,
        )

        # -----------------------------------------------------
        # 8. VERIFYING
        # -----------------------------------------------------

        tx.transition(TransactionState.VERIFYING)

        update_transaction_state(
            transaction_id,
            tx.state.value,
        )

        if block_mode:
            verified_data = reconstruct_object(
                object_id
            )

            if len(verified_data) != len(data):
                raise ValueError(
                    "Tamanho reconstruído diferente do esperado."
                )

            verified_hash = hashlib.sha256(
                verified_data
            ).hexdigest()

            if verified_hash != content_hash:
                raise ValueError(
                    "Hash reconstruído diferente do esperado."
                )

        # -----------------------------------------------------
        # JOURNAL: VERIFIED
        # -----------------------------------------------------

        update_transaction_journal(
            transaction_id,
            phase="VERIFIED",
            verified=True,
        )

        # -----------------------------------------------------
        # 9. COMMITTING
        # -----------------------------------------------------

        tx.transition(TransactionState.COMMITTING)

        update_transaction_state(
            transaction_id,
            tx.state.value,
        )

        if not block_mode:
            register_object(
                object_id=object_id,
                content_hash=content_hash,
                size=len(data),
                storage_path=object_path,
                namespace=namespace,
            )

            object_registered = True

            result = {
                **get_object(object_id),
                "storage_mode": "DIRECT",
                "transaction_id": transaction_id,
                "allocation": {
                    "logical_bytes": required_bytes,
                    "physical_delta": physical_delta,
                    "quota_mode": quota_mode,
                },
            }

        else:
            result = {
                "object_id": manifest["object_id"],
                "content_hash": content_hash,
                "namespace": namespace,
                "size": manifest["total_size"],
                "storage_path": None,
                "created_at": manifest["created_at"],
                "status": manifest["status"],
                "storage_mode": "BLOCKS",
                "block_count": manifest["block_count"],
                "transaction_id": transaction_id,
                "allocation": {
                    "logical_bytes": required_bytes,
                    "physical_delta": physical_delta,
                    "new_blocks": allocation["new_blocks"],
                    "existing_blocks": allocation["existing_blocks"],
                    "new_block_bytes": allocation["new_block_bytes"],
                    "quota_mode": quota_mode,
                },
            }

        # -----------------------------------------------------
        # PERSISTIR RESPOSTA IDEMPOTENTE
        # -----------------------------------------------------
        #
        # A resposta fica no metadata antes do commit marker.
        # Dessa forma, uma recuperação após crash consegue
        # reconstruir o resultado original da operação.

        if idempotency_key is not None:
            committed_metadata = {
                "size": required_bytes,
                "block_mode": block_mode,
                "block_size": allocation.get(
                    "block_size",
                    None,
                ),
                "physical_delta": physical_delta,
                "quota_mode": quota_mode,
                "idempotency_response": result,
            }

            update_transaction_metadata(
                transaction_id,
                committed_metadata,
            )

        # -----------------------------------------------------
        # JOURNAL: COMMIT MARKER
        # -----------------------------------------------------
        #
        # Este é o ponto que prova que os recursos da operação
        # chegaram ao commit. O recovery pode usar esta marca
        # para distinguir ROLLBACK de RECOVER COMMIT.

        update_transaction_journal(
            transaction_id,
            phase="COMMIT_MARKER",
            commit_marker=True,
        )

        # -----------------------------------------------------
        # 10. COMMITTED
        # -----------------------------------------------------

        tx.commit()

        update_transaction_state(
            transaction_id,
            tx.state.value,
        )

        return result

    except Exception as exc:
        # -----------------------------------------------------
        # 11. FAILED
        # -----------------------------------------------------

        error_message = (
            f"{type(exc).__name__}: {exc}"
        )

        tx.fail(error_message)

        update_transaction_state(
            transaction_id,
            tx.state.value,
            error=error_message,
        )

        # -----------------------------------------------------
        # 12. ROLLBACK
        # -----------------------------------------------------

        try:
            # Se um objeto DIRECT foi registrado antes da falha,
            # retirar sua entrada do registry.
            if object_registered:
                try:
                    remove_object_record(object_id)
                except Exception:
                    pass

            # -------------------------------------------------
            # HARD CLEANUP DO MANIFEST CRIADO PELA TRANSAÇÃO
            # -------------------------------------------------
            #
            # delete_manifest() é soft-delete e pertence ao
            # ciclo de vida normal.
            #
            # Rollback precisa remover definitivamente os
            # registros criados exclusivamente por esta tx.
            if manifest_created:
                try:
                    purge_manifest(object_id)
                except Exception:
                    pass

                try:
                    purge_object_record(object_id)
                except Exception:
                    pass

            # Remover somente arquivos DIRECT criados por esta tx.
            if created_direct_file is not None:
                try:
                    if created_direct_file.exists():
                        created_direct_file.unlink()
                except Exception:
                    pass

            # Blocos novos e sem referência podem ser removidos.
            if created_block_ids:
                try:
                    rebuild_block_ref_counts()
                except Exception:
                    pass

                for block_id in created_block_ids:
                    conn = None

                    try:
                        conn = connect()

                        row = conn.execute(
                            """
                            SELECT
                                block_id,
                                storage_path,
                                ref_count,
                                status
                            FROM blocks
                            WHERE block_id = ?
                            """,
                            (block_id,),
                        ).fetchone()

                        conn.close()
                        conn = None

                        if row is None:
                            continue

                        if row[2] != 0:
                            continue

                        block_path = Path(row[1])

                        # Primeiro torna o registro logicamente deletado.
                        # Assim, uma falha na remoção física não deixa
                        # o bloco marcado como ACTIVE.
                        mark_block_deleted(block_id)

                        # Depois remove o payload físico.
                        if block_path.exists():
                            block_path.unlink()

                        # Finalmente remove o registro do registry.
                        remove_block_record(block_id)

                    except Exception:
                        if conn is not None:
                            try:
                                conn.close()
                            except Exception:
                                pass
                        raise

            tx.rollback()

            update_transaction_state(
                transaction_id,
                tx.state.value,
                error=error_message,
            )

            update_transaction_journal(
                transaction_id,
                phase="ROLLBACK",
                verified=False,
                commit_marker=False,
            )

        except Exception as rollback_error:
            rollback_message = (
                f"{error_message}; "
                f"rollback_error="
                f"{type(rollback_error).__name__}: "
                f"{rollback_error}"
            )

            try:
                update_transaction_state(
                    transaction_id,
                    "FAILED",
                    error=rollback_message,
                )
            except Exception:
                pass

        raise

def get_object_data(object_id):
    obj = get_object(object_id)

    if obj is None:
        raise KeyError(f"Objeto não encontrado: {object_id}")

    if obj["status"] != "ACTIVE":
        raise ValueError(
            f"Objeto não está ACTIVE: {object_id}"
        )

    # BLOCKS:
    # recupera através do manifest e reconstrói o objeto.
    if obj["storage_path"] is None:
        from node.manifest import reconstruct_object

        data = reconstruct_object(object_id)

        if len(data) != obj["size"]:
            raise ValueError(
                "Tamanho reconstruído diferente do registry."
            )

        calculated_hash = hashlib.sha256(data).hexdigest()

        if calculated_hash != obj["content_hash"]:
            raise ValueError(
                "Hash reconstruído diferente do registry."
            )

        return data

    # DIRECT:
    # recupera diretamente do arquivo físico.
    path = Path(obj["storage_path"])

    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo do objeto não encontrado: {path}"
        )

    data = path.read_bytes()

    if len(data) != obj["size"]:
        raise ValueError(
            "Tamanho do objeto diferente do registry."
        )

    calculated_hash = hashlib.sha256(data).hexdigest()

    if calculated_hash != obj["content_hash"]:
        raise ValueError(
            "Hash do objeto diferente do registry."
        )

    return data
def verify_object(object_id):
    obj = get_object(object_id)

    if obj is None:
        return False, "NOT_FOUND"

    if obj["status"] != "ACTIVE":
        return False, "NOT_ACTIVE"

    # Objetos BLOCKS são verificados através do manifest
    # e da reconstrução integral do objeto.
    if obj["storage_path"] is None:
        try:
            from node.manifest import reconstruct_object

            data = reconstruct_object(object_id)

            calculated_hash = hashlib.sha256(data).hexdigest()

            if calculated_hash != obj["content_hash"]:
                return False, "HASH_MISMATCH"

            if len(data) != obj["size"]:
                return False, "SIZE_MISMATCH"

            return True, "OK_BLOCKS"

        except FileNotFoundError:
            return False, "BLOCK_NOT_FOUND"
        except ValueError as exc:
            return False, f"BLOCK_INTEGRITY_ERROR: {exc}"
        except Exception as exc:
            return False, f"VERIFY_ERROR: {type(exc).__name__}: {exc}"

    # Objetos DIRECT possuem arquivo físico próprio.
    path = Path(obj["storage_path"])

    if not path.exists():
        return False, "STORAGE_MISSING"

    try:
        data = path.read_bytes()
    except OSError:
        return False, "STORAGE_READ_ERROR"

    if len(data) != obj["size"]:
        return False, "SIZE_MISMATCH"

    calculated_hash = hashlib.sha256(data).hexdigest()

    if calculated_hash != obj["content_hash"]:
        return False, "HASH_MISMATCH"

    return True, "OK_DIRECT"
def delete_object_data(object_id):
    obj = get_object(object_id)

    if obj is None:
        return False, "NOT_FOUND"

    if obj["status"] == "DELETED":
        return False, "ALREADY_DELETED"

    # ---------------------------------------------------------
    # OBJECT BLOCKS
    # ---------------------------------------------------------
    # Objetos armazenados através de manifest possuem
    # referências físicas em manifest_blocks.
    #
    # Primeiro removemos o manifesto/referências para que
    # ref_count seja recalculado corretamente.
    if obj["storage_path"] is None:
        manifest = get_manifest(object_id)

        if manifest is None:
            return False, "MANIFEST_NOT_FOUND"

        if manifest["status"] == "DELETED":
            return False, "ALREADY_DELETED"

        if not delete_manifest(object_id):
            return False, "MANIFEST_DELETE_FAILED"

        if not delete_object(object_id):
            return False, "OBJECT_DELETE_FAILED"

        return True, "DELETED_BLOCKS"

    # ---------------------------------------------------------
    # DIRECT OBJECT
    # ---------------------------------------------------------
    if delete_object(object_id):
        return True, "DELETED_DIRECT"

    return False, "DELETE_FAILED"


def garbage_collect_blocks():
    removed = 0
    cleaned = 0

    candidates = delete_unreferenced_blocks()

    for block_id, storage_path in candidates:
        path = Path(storage_path)

        if not mark_block_deleted(block_id):
            continue

        if path.exists():
            path.unlink()
            removed += 1

        if remove_block_record(block_id):
            cleaned += 1

    return {
        "physical_removed": removed,
        "registry_cleaned": cleaned,
    }

def garbage_collect():
    removed_objects = 0
    removed_blocks = 0
    errors = []

    # ---------------------------------------------------------
    # 1. DIRECT OBJECTS
    # ---------------------------------------------------------
    # Remove arquivos físicos de objetos marcados como DELETED.
    conn = connect()

    rows = conn.execute("""
        SELECT object_id, storage_path, status
        FROM objects
        WHERE status = 'DELETED'
          AND storage_path IS NOT NULL
    """).fetchall()

    conn.close()

    for object_id, storage_path, status in rows:
        try:
            if storage_path:
                path = Path(storage_path)

                if path.exists():
                    path.unlink()

            removed_objects += 1

        except Exception as exc:
            errors.append({
                "type": "OBJECT",
                "object_id": object_id,
                "error": f"{type(exc).__name__}: {exc}",
            })

    # ---------------------------------------------------------
    # 2. BLOCKS
    # ---------------------------------------------------------
    # Blocks só podem ser removidos quando não possuem
    # nenhuma referência ativa.
    try:
        rebuild_block_ref_counts()

        orphan_blocks = list_unreferenced_blocks()

        for block_id, storage_path in orphan_blocks:

            try:
                if storage_path:
                    path = Path(storage_path)

                    if path.exists():
                        path.unlink()

                mark_block_deleted(block_id)
                remove_block_record(block_id)

                removed_blocks += 1

            except Exception as exc:
                errors.append({
                    "type": "BLOCK",
                    "block_id": block_id,
                    "error": f"{type(exc).__name__}: {exc}",
                })

    except Exception as exc:
        errors.append({
            "type": "BLOCK_GC",
            "error": f"{type(exc).__name__}: {exc}",
        })

    return {
        "removed_objects": removed_objects,
        "removed_blocks": removed_blocks,
        "errors": errors,
    }
def reconcile_storage():
    recovered = 0

    registered_ids = {
        row[0]
        for row in all_objects()
    }

    if not OBJECTS_DIR.exists():
        return recovered

    for path in OBJECTS_DIR.iterdir():
        if not path.is_file():
            continue

        object_id = path.name

        if object_id in registered_ids:
            continue

        data = path.read_bytes()
        content_hash = hashlib.sha256(data).hexdigest()

        if content_hash != object_id:
            continue

        if reconcile_object(
            object_id,
            content_hash,
            len(data),
            path,
        ):
            recovered += 1

    return recovered
