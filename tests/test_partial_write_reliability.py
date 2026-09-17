import hashlib
import os
from pathlib import Path

from node.block_manager import BLOCKS_DIR, calculate_hash, load_block
from node.registry import connect, register_block


def test_partial_write_is_detected():
    data = b"A" * 4096
    block_id = calculate_hash(data)
    block_path = BLOCKS_DIR / block_id

    partial = data[:1024]

    if block_path.exists():
        block_path.unlink()

    block_path.write_bytes(partial)

    register_block(
        block_id=block_id,
        content_hash=hashlib.sha256(data).hexdigest(),
        size=len(data),
        storage_path=block_path,
    )

    try:
        load_block(block_id)
    except ValueError as exc:
        assert "Tamanho do bloco inválido" in str(exc)
    finally:
        if block_path.exists():
            block_path.unlink()

        conn = connect()
        conn.execute(
            "DELETE FROM blocks WHERE block_id = ?",
            (block_id,),
        )
        conn.commit()
        conn.close()
