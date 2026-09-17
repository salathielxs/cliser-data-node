from node.object_manager import put_object, get_object_data
from node.registry import (
    connect,
    get_object,
    get_manifest,
)
from node.block_manager import load_block


def check(condition, message):
    if not condition:
        raise AssertionError(message)


NS_A = "iso-a"
NS_B = "iso-b"

DATA = (
    b"CLISER-NAMESPACE-ISOLATION-" * 10
)


def cleanup():
    conn = connect()

    try:
        conn.execute("BEGIN")

        # Localizar transações dos namespaces de teste.
        transaction_ids = [
            row[0]
            for row in conn.execute(
                """
                SELECT transaction_id
                FROM transactions
                WHERE namespace IN (?, ?)
                """,
                (NS_A, NS_B),
            ).fetchall()
        ]

        # transaction_journal possui ON DELETE CASCADE.
        # Remover transactions elimina seus journals associados.
        for transaction_id in transaction_ids:
            conn.execute(
                "DELETE FROM transactions WHERE transaction_id = ?",
                (transaction_id,),
            )

        # Remover apenas os objetos dos namespaces de teste.
        objects = conn.execute(
            """
            SELECT object_id
            FROM objects
            WHERE namespace IN (?, ?)
            """,
            (NS_A, NS_B),
        ).fetchall()

        for row in objects:
            object_id = row[0]

            conn.execute(
                "DELETE FROM manifest_blocks WHERE object_id = ?",
                (object_id,),
            )

            conn.execute(
                "DELETE FROM manifests WHERE object_id = ?",
                (object_id,),
            )

            conn.execute(
                "DELETE FROM objects WHERE object_id = ?",
                (object_id,),
            )

        conn.execute(
            "DELETE FROM quotas WHERE namespace IN (?, ?)",
            (NS_A, NS_B),
        )

        conn.execute(
            "DELETE FROM namespaces WHERE namespace IN (?, ?)",
            (NS_A, NS_B),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


cleanup()


# ---------------------------------------------------------
# 1. NAMESPACES
# ---------------------------------------------------------

from node.namespace_manager import create_namespace

create_namespace(NS_A)
create_namespace(NS_B)

print("NAMESPACE A: OK")
print("NAMESPACE B: OK")


# ---------------------------------------------------------
# 2. MESMO CONTEÚDO EM DOIS NAMESPACES
# ---------------------------------------------------------

result_a = put_object(
    DATA,
    namespace=NS_A,
)

result_b = put_object(
    DATA,
    namespace=NS_B,
)

object_a = result_a["object_id"]
object_b = result_b["object_id"]

check(
    object_a != object_b,
    "IDENTIDADE LÓGICA: FAIL",
)

print("OBJECT IDs DIFERENTES: OK")


# ---------------------------------------------------------
# 3. HASH DO CONTEÚDO
# ---------------------------------------------------------

record_a = get_object(object_a)
record_b = get_object(object_b)

check(
    record_a is not None,
    "OBJECT A: FAIL",
)

check(
    record_b is not None,
    "OBJECT B: FAIL",
)

check(
    record_a["content_hash"] == record_b["content_hash"],
    "CONTENT HASH: FAIL",
)

print("CONTENT HASH IGUAL: OK")


# ---------------------------------------------------------
# 4. NAMESPACE
# ---------------------------------------------------------

check(
    record_a["namespace"] == NS_A,
    "NAMESPACE A: FAIL",
)

check(
    record_b["namespace"] == NS_B,
    "NAMESPACE B: FAIL",
)

print("NAMESPACE ISOLATION: OK")


# ---------------------------------------------------------
# 5. MANIFESTS
# ---------------------------------------------------------

manifest_a = get_manifest(object_a)
manifest_b = get_manifest(object_b)

check(
    manifest_a is not None,
    "MANIFEST A: FAIL",
)

check(
    manifest_b is not None,
    "MANIFEST B: FAIL",
)

check(
    manifest_a["object_id"] == object_a,
    "MANIFEST A OBJECT: FAIL",
)

check(
    manifest_b["object_id"] == object_b,
    "MANIFEST B OBJECT: FAIL",
)

print("MANIFEST ISOLATION: OK")


# ---------------------------------------------------------
# 6. MESMO BLOCK FÍSICO
# ---------------------------------------------------------

blocks_a = manifest_a["blocks"]
blocks_b = manifest_b["blocks"]

check(
    len(blocks_a) == len(blocks_b),
    "BLOCK COUNT: FAIL",
)

block_ids_a = [
    block["block_id"]
    for block in blocks_a
]

block_ids_b = [
    block["block_id"]
    for block in blocks_b
]

check(
    block_ids_a == block_ids_b,
    "PHYSICAL DEDUPLICATION: FAIL",
)

print("SHARED PHYSICAL BLOCKS: OK")


# ---------------------------------------------------------
# 7. RECONSTRUÇÃO
# ---------------------------------------------------------

data_a = get_object_data(object_a)
data_b = get_object_data(object_b)

check(
    data_a == DATA,
    "RECONSTRUCTION A: FAIL",
)

check(
    data_b == DATA,
    "RECONSTRUCTION B: FAIL",
)

print("RECONSTRUCTION A: OK")
print("RECONSTRUCTION B: OK")


# ---------------------------------------------------------
# 8. REF COUNT
# ---------------------------------------------------------

conn = connect()

try:
    for block_id in block_ids_a:
        row = conn.execute(
            """
            SELECT ref_count
            FROM blocks
            WHERE block_id = ?
            """,
            (block_id,),
        ).fetchone()

        check(
            row is not None,
            f"BLOCK NÃO ENCONTRADO: {block_id}",
        )

        check(
            row[0] >= 2,
            f"REF COUNT INVÁLIDO: {block_id}",
        )

finally:
    conn.close()

print("BLOCK REF COUNT >= 2: OK")


print()
print("=" * 60)
print("NAMESPACE ISOLATION: OK")
print("=" * 60)
