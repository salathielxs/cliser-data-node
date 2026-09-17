import hashlib

from node.block_manager import store_block, load_block

from node.registry import (
    register_manifest,
    get_manifest,
    get_object,
)

DEFAULT_BLOCK_SIZE = 1024 * 1024
DEFAULT_NAMESPACE = "default"


def create_manifest(
    data: bytes,
    block_size: int = DEFAULT_BLOCK_SIZE,
    namespace: str = DEFAULT_NAMESPACE,
    object_id: str | None = None,
):
    if not isinstance(data, bytes):
        raise TypeError("data deve ser bytes.")

    if block_size <= 0:
        raise ValueError(
            "block_size deve ser maior que zero."
        )

    if not namespace:
        raise ValueError(
            "namespace inválido."
        )

    if not object_id:
        raise ValueError(
            "object_id é obrigatório."
        )

    content_hash = hashlib.sha256(data).hexdigest()

    blocks = []

    for index, offset in enumerate(
        range(0, len(data), block_size)
    ):
        chunk = data[offset:offset + block_size]

        block = store_block(chunk)

        blocks.append({
            "index": index,
            "block_id": block["block_id"],
            "size": block["size"],
        })

    register_manifest(
        object_id=object_id,
        content_hash=content_hash,
        total_size=len(data),
        block_size=block_size,
        block_count=len(blocks),
        blocks=blocks,
        namespace=namespace,
    )

    return get_manifest(object_id)


def reconstruct_object(object_id: str) -> bytes:
    manifest = get_manifest(object_id)

    if manifest is None:
        raise FileNotFoundError(
            "Manifest não encontrado."
        )

    if manifest["status"] != "ACTIVE":
        raise ValueError(
            "Manifest não está ACTIVE."
        )

    data = bytearray()

    for block in manifest["blocks"]:
        chunk = load_block(block["block_id"])
        data.extend(chunk)

    if len(data) != manifest["total_size"]:
        raise ValueError(
            "Tamanho reconstruído diferente do manifest."
        )

    calculated_hash = hashlib.sha256(data).hexdigest()

    obj = get_object(object_id)

    if obj is None:
        raise ValueError(
            "Objeto associado ao manifest não encontrado."
        )

    if calculated_hash != obj["content_hash"]:
        raise ValueError(
            "Integridade do objeto reconstruído inválida."
        )

    return bytes(data)
