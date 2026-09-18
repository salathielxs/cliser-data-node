import sqlite3
from pathlib import Path
from datetime import datetime, timezone


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "registry.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS namespaces (
            namespace TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            quota_bytes INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS objects (
            object_id TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            size INTEGER NOT NULL,
            storage_path TEXT,
            namespace TEXT NOT NULL DEFAULT 'default',
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE'
        );

        CREATE TABLE IF NOT EXISTS blocks (
            block_id TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            size INTEGER NOT NULL,
            storage_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            ref_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS manifests (
            object_id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL DEFAULT 'default',
            total_size INTEGER NOT NULL,
            block_size INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',

            FOREIGN KEY (object_id)
                REFERENCES objects(object_id)
        );

        CREATE TABLE IF NOT EXISTS manifest_blocks (
            object_id TEXT NOT NULL,
            block_index INTEGER NOT NULL,
            block_id TEXT NOT NULL,
            size INTEGER NOT NULL,

            PRIMARY KEY (
                object_id,
                block_index
            ),

            FOREIGN KEY (object_id)
                REFERENCES manifests(object_id)
                ON DELETE CASCADE,

            FOREIGN KEY (block_id)
                REFERENCES blocks(block_id)
        );

        CREATE TABLE IF NOT EXISTS quotas (
            namespace TEXT PRIMARY KEY,
            quota_bytes INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            object_id TEXT,
            namespace TEXT,
            operation TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error TEXT,
            metadata TEXT,
            idempotency_key TEXT,
            request_fingerprint TEXT
        );

        CREATE TABLE IF NOT EXISTS transaction_journal (
            transaction_id TEXT PRIMARY KEY,
            phase TEXT NOT NULL,
            commit_marker INTEGER NOT NULL DEFAULT 0,
            resources TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (transaction_id)
                REFERENCES transactions(transaction_id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS api_credentials (
            credential_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            identity_id TEXT NOT NULL,
            role TEXT NOT NULL,
            namespace TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS peer_authorizations (
            identity_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            namespace TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS replay_records (
            envelope_id TEXT PRIMARY KEY,
            source_peer_id TEXT NOT NULL,
            source_node_id TEXT NOT NULL,
            received_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_peer_authorizations_fingerprint
        ON peer_authorizations(fingerprint);

        CREATE INDEX IF NOT EXISTS idx_peer_authorizations_status
        ON peer_authorizations(status);

        CREATE INDEX IF NOT EXISTS idx_api_credentials_token_hash
        ON api_credentials(token_hash);

        CREATE INDEX IF NOT EXISTS idx_api_credentials_identity
        ON api_credentials(identity_id);

        CREATE INDEX IF NOT EXISTS idx_api_credentials_namespace
        ON api_credentials(namespace);

        CREATE INDEX IF NOT EXISTS idx_api_credentials_status
        ON api_credentials(status);


        CREATE INDEX IF NOT EXISTS idx_transaction_journal_phase
        ON transaction_journal(phase);

        CREATE INDEX IF NOT EXISTS idx_transaction_journal_commit
        ON transaction_journal(commit_marker);

        CREATE INDEX IF NOT EXISTS idx_transactions_state
        ON transactions(state);

        CREATE INDEX IF NOT EXISTS idx_transactions_object
        ON transactions(object_id);

        CREATE INDEX IF NOT EXISTS idx_transactions_namespace
        ON transactions(namespace);


        CREATE INDEX IF NOT EXISTS idx_objects_namespace
        ON objects(namespace);

        CREATE INDEX IF NOT EXISTS idx_objects_status
        ON objects(status);

        CREATE INDEX IF NOT EXISTS idx_manifests_namespace
        ON manifests(namespace);

        CREATE INDEX IF NOT EXISTS idx_manifests_status
        ON manifests(status);

        CREATE INDEX IF NOT EXISTS idx_manifest_blocks_block
        ON manifest_blocks(block_id);

        CREATE INDEX IF NOT EXISTS idx_blocks_status
        ON blocks(status);
    """)

    # ========================================================
    # MIGRATION: IDEMPOTENCY
    # ========================================================

    transaction_columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(transactions)"
        ).fetchall()
    }

    if "idempotency_key" not in transaction_columns:
        conn.execute("""
            ALTER TABLE transactions
            ADD COLUMN idempotency_key TEXT
        """)

    if "request_fingerprint" not in transaction_columns:
        conn.execute("""
            ALTER TABLE transactions
            ADD COLUMN request_fingerprint TEXT
        """)

    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_transactions_idempotency_unique
        ON transactions(
            namespace,
            operation,
            idempotency_key
        )
        WHERE idempotency_key IS NOT NULL
    """)

    conn.commit()

    return conn



# ============================================================
# TRANSPORT REPLAY PROTECTION
# ============================================================

def reserve_replay(
    envelope_id: str,
    source_peer_id: str,
    source_node_id: str,
    received_at: str,
    expires_at: str,
) -> bool:
    """
    Reserva um envelope para proteção contra replay.

    Lifecycle:

        envelope inexistente
            -> INSERT
            -> True

        envelope existente e ainda válido
            -> False

        envelope existente e expirado
            -> substituição atômica
            -> True

    BEGIN IMMEDIATE serializa concorrentes antes da decisão
    de reserva ou renovação.

    Invariante:

        N concorrentes para o mesmo envelope_id
            -> exatamente 1 vencedor
            -> demais retornam False
    """

    if not envelope_id:
        raise ValueError("envelope_id inválido.")

    if not source_peer_id:
        raise ValueError("source_peer_id inválido.")

    if not source_node_id:
        raise ValueError("source_node_id inválido.")

    if not received_at:
        raise ValueError("received_at inválido.")

    if not expires_at:
        raise ValueError("expires_at inválido.")

    conn = connect()

    try:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT
                source_peer_id,
                source_node_id,
                received_at,
                expires_at
            FROM replay_records
            WHERE envelope_id = ?
            """,
            (envelope_id,),
        ).fetchone()

        if row is None:
            conn.execute(
                """
                INSERT INTO replay_records
                (
                    envelope_id,
                    source_peer_id,
                    source_node_id,
                    received_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    envelope_id,
                    source_peer_id,
                    source_node_id,
                    received_at,
                    expires_at,
                ),
            )

            conn.commit()
            return True

        existing_expires_at = row[3]

        if existing_expires_at < received_at:
            conn.execute(
                """
                UPDATE replay_records
                SET
                    source_peer_id = ?,
                    source_node_id = ?,
                    received_at = ?,
                    expires_at = ?
                WHERE envelope_id = ?
                """,
                (
                    source_peer_id,
                    source_node_id,
                    received_at,
                    expires_at,
                    envelope_id,
                ),
            )

            conn.commit()
            return True

        conn.rollback()
        return False

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def register_object(
    object_id,
    content_hash,
    size,
    storage_path,
    namespace="default",
):
    conn = connect()

    created_at = datetime.now(timezone.utc).isoformat()

    conn.execute("""
        INSERT INTO objects
        (
            object_id,
            content_hash,
            size,
            storage_path,
            namespace,
            created_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
        ON CONFLICT(object_id)
        DO UPDATE SET
            content_hash = excluded.content_hash,
            size = excluded.size,
            storage_path = excluded.storage_path,
            namespace = excluded.namespace,
            status = 'ACTIVE'
    """, (
        object_id,
        content_hash,
        size,
        str(storage_path) if storage_path else None,
        namespace,
        created_at,
    ))

    conn.commit()
    conn.close()


def get_object(object_id):
    conn = connect()

    row = conn.execute("""
        SELECT
            object_id,
            content_hash,
            size,
            storage_path,
            namespace,
            created_at,
            status
        FROM objects
        WHERE object_id = ?
    """, (object_id,)).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "object_id": row[0],
        "content_hash": row[1],
        "size": row[2],
        "storage_path": row[3],
        "namespace": row[4],
        "created_at": row[5],
        "status": row[6],
    }


def list_objects(namespace=None):
    conn = connect()

    if namespace is None:
        rows = conn.execute("""
            SELECT
                object_id,
                size,
                namespace,
                created_at,
                status
            FROM objects
            ORDER BY created_at DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT
                object_id,
                size,
                namespace,
                created_at,
                status
            FROM objects
            WHERE namespace = ?
            ORDER BY created_at DESC
        """, (namespace,)).fetchall()

    conn.close()

    return rows


def count_objects(namespace=None):
    conn = connect()

    if namespace is None:
        result = conn.execute(
            "SELECT COUNT(*) FROM objects"
        ).fetchone()[0]
    else:
        result = conn.execute(
            """
            SELECT COUNT(*)
            FROM objects
            WHERE namespace = ?
            """,
            (namespace,),
        ).fetchone()[0]

    conn.close()

    return result


def delete_object(object_id):
    conn = connect()

    cursor = conn.execute("""
        UPDATE objects
        SET status = 'DELETED'
        WHERE object_id = ?
          AND status = 'ACTIVE'
    """, (object_id,))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    return changed > 0


def all_objects():
    conn = connect()

    rows = conn.execute("""
        SELECT
            object_id,
            content_hash,
            size,
            storage_path,
            status
        FROM objects
    """).fetchall()

    conn.close()

    return rows


def deleted_objects():
    conn = connect()

    rows = conn.execute("""
        SELECT
            object_id,
            storage_path
        FROM objects
        WHERE status = 'DELETED'
    """).fetchall()

    conn.close()

    return rows


def remove_object_record(object_id):
    conn = connect()

    cursor = conn.execute("""
        DELETE FROM objects
        WHERE object_id = ?
          AND status = 'DELETED'
    """, (object_id,))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    return changed > 0


def reconcile_object(
    object_id,
    content_hash,
    size,
    storage_path,
    namespace="default",
):
    conn = connect()

    existing = conn.execute("""
        SELECT object_id
        FROM objects
        WHERE object_id = ?
    """, (object_id,)).fetchone()

    if existing:
        conn.close()
        return False

    created_at = datetime.now(timezone.utc).isoformat()

    conn.execute("""
        INSERT INTO objects
        (
            object_id,
            content_hash,
            size,
            storage_path,
            namespace,
            created_at,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
    """, (
        object_id,
        content_hash,
        size,
        str(storage_path),
        namespace,
        created_at,
    ))

    conn.commit()
    conn.close()

    return True


# ============================================================
# BLOCKS
# ============================================================

def register_block(
    block_id,
    content_hash,
    size,
    storage_path,
):
    conn = connect()

    created_at = datetime.now(timezone.utc).isoformat()

    conn.execute("""
        INSERT INTO blocks
        (
            block_id,
            content_hash,
            size,
            storage_path,
            created_at,
            status,
            ref_count
        )
        VALUES (?, ?, ?, ?, ?, 'ACTIVE', 0)
        ON CONFLICT(block_id)
        DO UPDATE SET
            content_hash = excluded.content_hash,
            size = excluded.size,
            storage_path = excluded.storage_path,
            status = 'ACTIVE'
    """, (
        block_id,
        content_hash,
        size,
        str(storage_path),
        created_at,
    ))

    conn.commit()
    conn.close()


def get_block(block_id):
    conn = connect()

    row = conn.execute("""
        SELECT
            block_id,
            content_hash,
            size,
            storage_path,
            created_at,
            status,
            ref_count
        FROM blocks
        WHERE block_id = ?
    """, (block_id,)).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "block_id": row[0],
        "content_hash": row[1],
        "size": row[2],
        "storage_path": row[3],
        "created_at": row[4],
        "status": row[5],
        "ref_count": row[6],
    }


def list_unreferenced_blocks():
    conn = connect()

    rows = conn.execute("""
        SELECT
            block_id,
            storage_path
        FROM blocks
        WHERE ref_count = 0
          AND status = 'ACTIVE'
    """).fetchall()

    conn.close()

    return rows


def delete_unreferenced_blocks():
    return list_unreferenced_blocks()


def increment_block_ref(block_id):
    conn = connect()

    conn.execute("""
        UPDATE blocks
        SET ref_count = ref_count + 1
        WHERE block_id = ?
    """, (block_id,))

    conn.commit()
    conn.close()


def decrement_block_ref(block_id):
    conn = connect()

    conn.execute("""
        UPDATE blocks
        SET ref_count = CASE
            WHEN ref_count > 0 THEN ref_count - 1
            ELSE 0
        END
        WHERE block_id = ?
    """, (block_id,))

    conn.commit()
    conn.close()


def get_block_ref_count(block_id):
    conn = connect()

    row = conn.execute("""
        SELECT ref_count
        FROM blocks
        WHERE block_id = ?
    """, (block_id,)).fetchone()

    conn.close()

    if row is None:
        return None

    return row[0]


def rebuild_block_ref_counts():
    conn = connect()

    conn.execute("""
        UPDATE blocks
        SET ref_count = (
            SELECT COUNT(*)
            FROM manifest_blocks
            WHERE manifest_blocks.block_id = blocks.block_id
        )
    """)

    conn.commit()
    conn.close()


def verify_block_ref_counts():
    conn = connect()

    rows = conn.execute("""
        SELECT
            b.block_id,
            b.ref_count,
            COUNT(mb.block_id) AS calculated_refs
        FROM blocks b
        LEFT JOIN manifest_blocks mb
            ON mb.block_id = b.block_id
        GROUP BY b.block_id
        ORDER BY b.block_id
    """).fetchall()

    conn.close()

    return rows


def mark_block_deleted(block_id):
    conn = connect()

    cursor = conn.execute("""
        UPDATE blocks
        SET status = 'DELETED'
        WHERE block_id = ?
          AND ref_count = 0
          AND status = 'ACTIVE'
    """, (block_id,))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    return changed > 0


def remove_block_record(block_id):
    conn = connect()

    cursor = conn.execute("""
        DELETE FROM blocks
        WHERE block_id = ?
          AND status = 'DELETED'
          AND ref_count = 0
    """, (block_id,))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    return changed > 0


# ============================================================
# MANIFESTS
# ============================================================

def register_manifest(
    object_id,
    content_hash,
    total_size,
    block_size,
    block_count,
    blocks,
    namespace="default",
):
    from datetime import datetime, timezone

    if not object_id:
        raise ValueError("object_id inválido.")

    if not content_hash:
        raise ValueError("content_hash inválido.")

    if not namespace:
        raise ValueError("namespace inválido.")

    created_at = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        conn.execute("BEGIN")

        # O object_id identifica a referência lógica.
        # O content_hash identifica o conteúdo.
        conn.execute("""
            INSERT INTO objects
            (
                object_id,
                content_hash,
                size,
                storage_path,
                namespace,
                created_at,
                status
            )
            VALUES (?, ?, ?, NULL, ?, ?, 'ACTIVE')
            ON CONFLICT(object_id)
            DO UPDATE SET
                content_hash = excluded.content_hash,
                size = excluded.size,
                namespace = excluded.namespace,
                status = 'ACTIVE'
        """, (
            object_id,
            content_hash,
            total_size,
            namespace,
            created_at,
        ))

        # Remove manifesto anterior deste object_id lógico.
        conn.execute(
            "DELETE FROM manifest_blocks WHERE object_id = ?",
            (object_id,)
        )

        conn.execute(
            "DELETE FROM manifests WHERE object_id = ?",
            (object_id,)
        )

        conn.execute("""
            INSERT INTO manifests
            (
                object_id,
                namespace,
                total_size,
                block_size,
                block_count,
                created_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
        """, (
            object_id,
            namespace,
            total_size,
            block_size,
            block_count,
            created_at,
        ))

        for block in blocks:
            conn.execute("""
                INSERT INTO manifest_blocks
                (
                    object_id,
                    block_index,
                    block_id,
                    size
                )
                VALUES (?, ?, ?, ?)
            """, (
                object_id,
                block["index"],
                block["block_id"],
                block["size"],
            ))

        # ref_count representa o número global de referências
        # físicas ativas através dos manifests.
        conn.execute("""
            UPDATE blocks
            SET ref_count = (
                SELECT COUNT(*)
                FROM manifest_blocks mb
                WHERE mb.block_id = blocks.block_id
            )
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_manifest(object_id):
    conn = connect()

    manifest = conn.execute("""
        SELECT
            object_id,
            namespace,
            total_size,
            block_size,
            block_count,
            created_at,
            status
        FROM manifests
        WHERE object_id = ?
    """, (object_id,)).fetchone()

    if manifest is None:
        conn.close()
        return None

    rows = conn.execute("""
        SELECT
            block_index,
            block_id,
            size
        FROM manifest_blocks
        WHERE object_id = ?
        ORDER BY block_index
    """, (object_id,)).fetchall()

    conn.close()

    return {
        "object_id": manifest[0],
        "namespace": manifest[1],
        "total_size": manifest[2],
        "block_size": manifest[3],
        "block_count": manifest[4],
        "created_at": manifest[5],
        "status": manifest[6],
        "blocks": [
            {
                "index": row[0],
                "block_id": row[1],
                "size": row[2],
            }
            for row in rows
        ],
    }


def delete_manifest(object_id):
    conn = connect()

    manifest = conn.execute("""
        SELECT object_id
        FROM manifests
        WHERE object_id = ?
          AND status = 'ACTIVE'
    """, (object_id,)).fetchone()

    if manifest is None:
        conn.close()
        return False

    try:
        conn.execute("BEGIN")

        conn.execute("""
            UPDATE manifests
            SET status = 'DELETED'
            WHERE object_id = ?
        """, (object_id,))

        conn.execute("""
            DELETE FROM manifest_blocks
            WHERE object_id = ?
        """, (object_id,))

        conn.execute("""
            UPDATE blocks
            SET ref_count = (
                SELECT COUNT(*)
                FROM manifest_blocks
                WHERE manifest_blocks.block_id = blocks.block_id
            )
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return True


# ============================================================
# QUOTAS
# ============================================================

def register_quota(
    namespace,
    quota_bytes,
    created_at,
):
    if not namespace:
        raise ValueError("namespace inválido.")

    if quota_bytes < 0:
        raise ValueError(
            "quota_bytes não pode ser negativo."
        )

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
        created_at,
    ))

    conn.commit()
    conn.close()


def get_quota(namespace):
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

    return row


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

    return rows


def list_objects_by_namespace(namespace):
    """
    Lista objetos ativos pertencentes a um namespace.
    """
    if not namespace:
        raise ValueError("namespace inválido.")

    conn = connect()

    rows = conn.execute("""
        SELECT
            object_id,
            content_hash,
            size,
            storage_path,
            namespace,
            created_at,
            status
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
        ORDER BY created_at ASC
    """, (namespace,)).fetchall()

    conn.close()

    return [
        {
            "object_id": row[0],
            "content_hash": row[1],
            "size": row[2],
            "storage_path": row[3],
            "namespace": row[4],
            "created_at": row[5],
            "status": row[6],
        }
        for row in rows
    ]


def namespace_stats(namespace):
    """
    Estatísticas lógicas de um namespace.
    """
    if not namespace:
        raise ValueError("namespace inválido.")

    conn = connect()

    objects = conn.execute("""
        SELECT COUNT(*)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()[0]

    logical_bytes = conn.execute("""
        SELECT COALESCE(SUM(size), 0)
        FROM objects
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()[0]

    manifests = conn.execute("""
        SELECT COUNT(*)
        FROM manifests
        WHERE namespace = ?
          AND status = 'ACTIVE'
    """, (namespace,)).fetchone()[0]

    conn.close()

    return {
        "namespace": namespace,
        "objects": objects,
        "logical_bytes": logical_bytes,
        "manifests": manifests,
    }


def list_namespaces():
    """
    Retorna todos os namespaces que possuem objetos,
    manifests ou quotas registrados.
    """
    conn = connect()

    rows = conn.execute("""
        SELECT namespace
        FROM (
            SELECT namespace FROM objects
            UNION
            SELECT namespace FROM manifests
            UNION
            SELECT namespace FROM quotas
        )
        WHERE namespace IS NOT NULL
          AND namespace != ''
        ORDER BY namespace
    """).fetchall()

    conn.close()

    return [row[0] for row in rows]


def create_namespace(namespace, quota_bytes=0):
    from datetime import datetime, timezone

    if not namespace:
        raise ValueError("namespace inválido.")

    if quota_bytes < 0:
        raise ValueError("quota_bytes não pode ser negativo.")

    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        conn.execute("""
            INSERT INTO namespaces
            (
                namespace,
                status,
                quota_bytes,
                created_at,
                updated_at
            )
            VALUES (?, 'ACTIVE', ?, ?, ?)
        """, (
            namespace,
            quota_bytes,
            now,
            now,
        ))

        conn.commit()

    finally:
        conn.close()


def get_namespace(namespace):
    if not namespace:
        raise ValueError("namespace inválido.")

    conn = connect()

    row = conn.execute("""
        SELECT
            namespace,
            status,
            quota_bytes,
            created_at,
            updated_at
        FROM namespaces
        WHERE namespace = ?
    """, (namespace,)).fetchone()

    conn.close()

    if row is None:
        return None

    return {
        "namespace": row[0],
        "status": row[1],
        "quota_bytes": row[2],
        "created_at": row[3],
        "updated_at": row[4],
    }


def list_namespace_records():
    conn = connect()

    rows = conn.execute("""
        SELECT
            namespace,
            status,
            quota_bytes,
            created_at,
            updated_at
        FROM namespaces
        ORDER BY namespace
    """).fetchall()

    conn.close()

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


def set_namespace_status(namespace, status):
    from datetime import datetime, timezone

    allowed = {"ACTIVE", "DISABLED"}

    if status not in allowed:
        raise ValueError(
            f"status inválido. Use: {sorted(allowed)}"
        )

    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    cursor = conn.execute("""
        UPDATE namespaces
        SET status = ?,
            updated_at = ?
        WHERE namespace = ?
    """, (
        status,
        now,
        namespace,
    ))

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        raise KeyError(
            f"Namespace não encontrado: {namespace}"
        )


# ============================================================
# TRANSACTIONS
# ============================================================

def create_transaction(
    transaction_id,
    operation,
    state,
    object_id=None,
    namespace=None,
    metadata=None,
):
    import json

    conn = connect()

    now = datetime.now(timezone.utc).isoformat()

    metadata_json = (
        json.dumps(metadata, sort_keys=True)
        if metadata is not None
        else None
    )

    conn.execute("""
        INSERT INTO transactions
        (
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at,
            error,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
    """, (
        transaction_id,
        object_id,
        namespace,
        operation,
        state,
        now,
        now,
        metadata_json,
    ))

    conn.commit()
    conn.close()

    return get_transaction(transaction_id)



def create_idempotent_transaction(
    transaction_id,
    operation,
    state,
    object_id=None,
    namespace=None,
    metadata=None,
    idempotency_key=None,
    request_fingerprint=None,
):
    """
    Reserva atomicamente uma transação associada a uma Idempotency-Key.

    Retorno:
        {
            "created": True|False,
            "transaction": {...}
        }

    created=True:
        esta requisição criou a reserva.

    created=False:
        já existe uma transação para a mesma combinação:
        namespace + operation + idempotency_key.
    """
    import json
    import sqlite3

    if not idempotency_key:
        raise ValueError(
            "idempotency_key é obrigatório para "
            "create_idempotent_transaction"
        )

    conn = connect()

    now = datetime.now(timezone.utc).isoformat()

    metadata_json = (
        json.dumps(metadata, sort_keys=True)
        if metadata is not None
        else None
    )

    try:
        conn.execute("""
            INSERT INTO transactions
            (
                transaction_id,
                object_id,
                namespace,
                operation,
                state,
                created_at,
                updated_at,
                error,
                metadata,
                idempotency_key,
                request_fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
        """, (
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            now,
            now,
            metadata_json,
            idempotency_key,
            request_fingerprint,
        ))

        conn.commit()

        created = True

    except sqlite3.IntegrityError:
        conn.rollback()
        created = False

    conn.close()

    if created:
        return {
            "created": True,
            "transaction": get_transaction(transaction_id),
        }

    existing = get_idempotent_transaction(
        namespace=namespace,
        operation=operation,
        idempotency_key=idempotency_key,
    )

    if existing is None:
        raise RuntimeError(
            "Falha ao localizar transação idempotente "
            "após conflito de unicidade"
        )

    return {
        "created": False,
        "transaction": existing,
    }


def get_idempotent_transaction(
    namespace,
    operation,
    idempotency_key,
):
    """
    Localiza uma transação pela chave idempotente.

    O escopo atual da chave é:

        namespace + operation + idempotency_key
    """
    import json

    if not idempotency_key:
        return None

    conn = connect()

    row = conn.execute("""
        SELECT
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at,
            error,
            metadata,
            idempotency_key,
            request_fingerprint
        FROM transactions
        WHERE namespace = ?
          AND operation = ?
          AND idempotency_key = ?
        LIMIT 1
    """, (
        namespace,
        operation,
        idempotency_key,
    )).fetchone()

    conn.close()

    if row is None:
        return None

    metadata = None

    if row[8]:
        metadata = json.loads(row[8])

    return {
        "transaction_id": row[0],
        "object_id": row[1],
        "namespace": row[2],
        "operation": row[3],
        "state": row[4],
        "created_at": row[5],
        "updated_at": row[6],
        "error": row[7],
        "metadata": metadata,
        "idempotency_key": row[9],
        "request_fingerprint": row[10],
    }


def update_transaction_metadata(
    transaction_id,
    metadata,
):
    """
    Substitui o metadata JSON da transação.
    """
    import json

    conn = connect()

    updated_at = datetime.now(timezone.utc).isoformat()

    metadata_json = (
        json.dumps(metadata, sort_keys=True)
        if metadata is not None
        else None
    )

    cursor = conn.execute("""
        UPDATE transactions
        SET
            metadata = ?,
            updated_at = ?
        WHERE transaction_id = ?
    """, (
        metadata_json,
        updated_at,
        transaction_id,
    ))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    if not changed:
        raise KeyError(
            f"Transaction não encontrada: {transaction_id}"
        )

    return get_transaction(transaction_id)


def get_transaction(transaction_id):
    import json

    conn = connect()

    row = conn.execute("""
        SELECT
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at,
            error,
            metadata,
            idempotency_key,
            request_fingerprint
        FROM transactions
        WHERE transaction_id = ?
    """, (transaction_id,)).fetchone()

    conn.close()

    if row is None:
        return None

    metadata = None

    if row[8]:
        metadata = json.loads(row[8])

    return {
        "transaction_id": row[0],
        "object_id": row[1],
        "namespace": row[2],
        "operation": row[3],
        "state": row[4],
        "created_at": row[5],
        "updated_at": row[6],
        "error": row[7],
        "metadata": metadata,
        "idempotency_key": row[9],
        "request_fingerprint": row[10],
    }


def update_transaction_state(
    transaction_id,
    state,
    error=None,
):
    conn = connect()

    updated_at = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute("""
        UPDATE transactions
        SET
            state = ?,
            updated_at = ?,
            error = ?
        WHERE transaction_id = ?
    """, (
        state,
        updated_at,
        error,
        transaction_id,
    ))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    if not changed:
        raise KeyError(
            f"Transaction não encontrada: {transaction_id}"
        )

    return get_transaction(transaction_id)


def list_transactions(
    state=None,
    namespace=None,
):
    conn = connect()

    query = """
        SELECT
            transaction_id,
            object_id,
            namespace,
            operation,
            state,
            created_at,
            updated_at,
            error
        FROM transactions
        WHERE 1 = 1
    """

    params = []

    if state is not None:
        query += " AND state = ?"
        params.append(state)

    if namespace is not None:
        query += " AND namespace = ?"
        params.append(namespace)

    query += " ORDER BY created_at DESC"

    rows = conn.execute(
        query,
        params,
    ).fetchall()

    conn.close()

    return rows



def create_transaction_journal(
    transaction_id,
    phase,
    resources=None,
    verified=False,
):
    from datetime import datetime, timezone
    import json

    now = datetime.now(timezone.utc).isoformat()

    if isinstance(resources, (dict, list)):
        resources = json.dumps(
            resources,
            ensure_ascii=False,
            sort_keys=True,
        )

    conn = connect()

    conn.execute(
        """
        INSERT INTO transaction_journal (
            transaction_id,
            phase,
            commit_marker,
            resources,
            verified,
            created_at,
            updated_at
        )
        VALUES (?, ?, 0, ?, ?, ?, ?)
        """,
        (
            transaction_id,
            phase,
            resources,
            1 if verified else 0,
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()


def update_transaction_journal(
    transaction_id,
    phase=None,
    resources=None,
    verified=None,
    commit_marker=None,
):
    from datetime import datetime, timezone
    import json

    now = datetime.now(timezone.utc).isoformat()

    fields = []
    params = []

    if phase is not None:
        fields.append("phase = ?")
        params.append(phase)

    if resources is not None:
        if isinstance(resources, (dict, list)):
            resources = json.dumps(
                resources,
                ensure_ascii=False,
                sort_keys=True,
            )

        fields.append("resources = ?")
        params.append(resources)

    if verified is not None:
        fields.append("verified = ?")
        params.append(1 if verified else 0)

    if commit_marker is not None:
        fields.append("commit_marker = ?")
        params.append(1 if commit_marker else 0)

    fields.append("updated_at = ?")
    params.append(now)

    params.append(transaction_id)

    conn = connect()

    cursor = conn.execute(
        f"""
        UPDATE transaction_journal
        SET {", ".join(fields)}
        WHERE transaction_id = ?
        """,
        params,
    )

    conn.commit()
    changed = cursor.rowcount
    conn.close()

    return changed > 0


def get_transaction_journal(transaction_id):
    conn = connect()

    row = conn.execute(
        """
        SELECT
            transaction_id,
            phase,
            commit_marker,
            resources,
            verified,
            created_at,
            updated_at
        FROM transaction_journal
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    import json

    resources = row[3]

    if resources:
        try:
            resources = json.loads(resources)
        except Exception:
            pass

    return {
        "transaction_id": row[0],
        "phase": row[1],
        "commit_marker": bool(row[2]),
        "resources": resources,
        "verified": bool(row[4]),
        "created_at": row[5],
        "updated_at": row[6],
    }


def delete_transaction_journal(transaction_id):
    conn = connect()

    cursor = conn.execute(
        """
        DELETE FROM transaction_journal
        WHERE transaction_id = ?
        """,
        (transaction_id,),
    )

    conn.commit()
    changed = cursor.rowcount
    conn.close()

    return changed > 0

def delete_transaction(transaction_id):
    conn = connect()

    cursor = conn.execute("""
        DELETE FROM transactions
        WHERE transaction_id = ?
    """, (transaction_id,))

    conn.commit()

    changed = cursor.rowcount

    conn.close()

    return changed > 0


def purge_manifest(object_id):
    """
    Remove definitivamente o manifesto e suas relações.
    Uso exclusivo para rollback/limpeza interna.
    """
    conn = connect()

    try:
        conn.execute("BEGIN")

        conn.execute("""
            DELETE FROM manifest_blocks
            WHERE object_id = ?
        """, (object_id,))

        cursor = conn.execute("""
            DELETE FROM manifests
            WHERE object_id = ?
        """, (object_id,))

        # Mantém a invariável:
        # ref_count == número real de referências em manifest_blocks.
        conn.execute("""
            UPDATE blocks
            SET ref_count = (
                SELECT COUNT(*)
                FROM manifest_blocks
                WHERE manifest_blocks.block_id = blocks.block_id
            )
        """)

        conn.commit()

        return cursor.rowcount > 0

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def purge_object_record(object_id):
    """
    Remove definitivamente o registro do objeto.
    Uso exclusivo para rollback/limpeza interna.
    """
    conn = connect()

    try:
        conn.execute("BEGIN")

        cursor = conn.execute("""
            DELETE FROM objects
            WHERE object_id = ?
        """, (object_id,))

        conn.commit()

        return cursor.rowcount > 0

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ============================================================
# PEER AUTHORIZATIONS
# ============================================================

def register_peer_authorization(
    identity_id: str,
    fingerprint: str,
    role: str,
    namespace: str | None = None,
    status: str = "ACTIVE",
):
    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        conn.execute(
            """
            INSERT INTO peer_authorizations (
                identity_id,
                fingerprint,
                role,
                namespace,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identity_id,
                fingerprint,
                role,
                namespace,
                status,
                now,
                now,
            ),
        )

        conn.commit()

    finally:
        conn.close()


def get_peer_authorization_by_identity(
    identity_id: str,
):
    conn = connect()

    try:
        row = conn.execute(
            """
            SELECT
                identity_id,
                fingerprint,
                role,
                namespace,
                status,
                created_at,
                updated_at
            FROM peer_authorizations
            WHERE identity_id = ?
            LIMIT 1
            """,
            (identity_id,),
        ).fetchone()

        if row is None:
            return None

        return {
            "identity_id": row[0],
            "fingerprint": row[1],
            "role": row[2],
            "namespace": row[3],
            "status": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    finally:
        conn.close()


def get_peer_authorization_by_fingerprint(
    fingerprint: str,
):
    conn = connect()

    try:
        row = conn.execute(
            """
            SELECT
                identity_id,
                fingerprint,
                role,
                namespace,
                status,
                created_at,
                updated_at
            FROM peer_authorizations
            WHERE fingerprint = ?
            LIMIT 1
            """,
            (fingerprint,),
        ).fetchone()

        if row is None:
            return None

        return {
            "identity_id": row[0],
            "fingerprint": row[1],
            "role": row[2],
            "namespace": row[3],
            "status": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    finally:
        conn.close()


def revoke_peer_authorization(
    identity_id: str,
):
    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        cursor = conn.execute(
            """
            UPDATE peer_authorizations
            SET
                status = 'REVOKED',
                updated_at = ?
            WHERE identity_id = ?
            """,
            (
                now,
                identity_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def reactivate_peer_authorization(
    identity_id: str,
    fingerprint: str | None = None,
    role: str | None = None,
    namespace: str | None = None,
):
    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        current = conn.execute(
            """
            SELECT
                identity_id,
                fingerprint,
                role,
                namespace,
                status
            FROM peer_authorizations
            WHERE identity_id = ?
            LIMIT 1
            """,
            (identity_id,),
        ).fetchone()

        if current is None:
            return False

        current_fingerprint = current[1]
        current_role = current[2]
        current_namespace = current[3]

        new_fingerprint = (
            fingerprint
            if fingerprint is not None
            else current_fingerprint
        )

        new_role = (
            role
            if role is not None
            else current_role
        )

        new_namespace = (
            namespace
            if namespace is not None
            else current_namespace
        )

        cursor = conn.execute(
            """
            UPDATE peer_authorizations
            SET
                fingerprint = ?,
                role = ?,
                namespace = ?,
                status = 'ACTIVE',
                updated_at = ?
            WHERE identity_id = ?
            """,
            (
                new_fingerprint,
                new_role,
                new_namespace,
                now,
                identity_id,
            ),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()



def list_peer_authorizations():
    conn = connect()

    try:
        rows = conn.execute(
            """
            SELECT
                identity_id,
                fingerprint,
                role,
                namespace,
                status,
                created_at,
                updated_at
            FROM peer_authorizations
            ORDER BY created_at
            """
        ).fetchall()

        return [
            {
                "identity_id": row[0],
                "fingerprint": row[1],
                "role": row[2],
                "namespace": row[3],
                "status": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
            for row in rows
        ]

    finally:
        conn.close()



# ============================================================
# API CREDENTIALS
# ============================================================

def register_api_credential(
    credential_id: str,
    token_hash: str,
    identity_id: str,
    role: str,
    namespace: str | None = None,
    status: str = "ACTIVE",
):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        conn.execute(
            """
            INSERT INTO api_credentials (
                credential_id,
                token_hash,
                identity_id,
                role,
                namespace,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                credential_id,
                token_hash,
                identity_id,
                role,
                namespace,
                status,
                now,
                now,
            ),
        )

        conn.commit()

    finally:
        conn.close()


def get_api_credential_by_hash(token_hash: str):
    conn = connect()

    try:
        row = conn.execute(
            """
            SELECT
                credential_id,
                token_hash,
                identity_id,
                role,
                namespace,
                status,
                created_at,
                updated_at
            FROM api_credentials
            WHERE token_hash = ?
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()

        if row is None:
            return None

        return {
            "credential_id": row[0],
            "token_hash": row[1],
            "identity_id": row[2],
            "role": row[3],
            "namespace": row[4],
            "status": row[5],
            "created_at": row[6],
            "updated_at": row[7],
        }

    finally:
        conn.close()


def revoke_api_credential(credential_id: str):
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    conn = connect()

    try:
        cursor = conn.execute(
            """
            UPDATE api_credentials
            SET
                status = 'REVOKED',
                updated_at = ?
            WHERE credential_id = ?
            """,
            (now, credential_id),
        )

        conn.commit()

        return cursor.rowcount > 0

    finally:
        conn.close()


def list_api_credentials():
    conn = connect()

    try:
        rows = conn.execute(
            """
            SELECT
                credential_id,
                identity_id,
                role,
                namespace,
                status,
                created_at,
                updated_at
            FROM api_credentials
            ORDER BY created_at
            """
        ).fetchall()

        return [
            {
                "credential_id": row[0],
                "identity_id": row[1],
                "role": row[2],
                "namespace": row[3],
                "status": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }
            for row in rows
        ]

    finally:
        conn.close()
