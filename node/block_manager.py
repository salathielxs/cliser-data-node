import hashlib
from pathlib import Path

from node.storage import BASE_DIR
from node.registry import register_block, get_block

BLOCKS_DIR = BASE_DIR / "storage" / "blocks"

BLOCKS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_block(data: bytes):
    content_hash = calculate_hash(data)

    block_id = content_hash

    block_path = BLOCKS_DIR / block_id

    if not block_path.exists():
        block_path.write_bytes(data)

    register_block(
        block_id=block_id,
        content_hash=content_hash,
        size=len(data),
        storage_path=block_path
    )

    return get_block(block_id)


def load_block(block_id: str) -> bytes:
    block = get_block(block_id)

    if block is None:
        raise FileNotFoundError("Bloco não registrado.")

    if block["status"] != "ACTIVE":
        raise ValueError("Bloco não está ACTIVE.")

    path = Path(block["storage_path"])

    if not path.exists():
        raise FileNotFoundError("Bloco ausente no Storage.")

    data = path.read_bytes()

    if len(data) != block["size"]:
        raise ValueError("Tamanho do bloco inválido.")

    calculated_hash = calculate_hash(data)

    if calculated_hash != block["content_hash"]:
        raise ValueError("Integridade do bloco inválida.")

    return data
