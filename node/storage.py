import hashlib
from pathlib import Path

from node.registry import register_object

BASE_DIR = Path(__file__).resolve().parent.parent
OBJECTS_DIR = BASE_DIR / "storage" / "objects"

OBJECTS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_object(data: bytes) -> str:
    content_hash = calculate_hash(data)
    object_id = content_hash

    object_path = OBJECTS_DIR / object_id

    if not object_path.exists():
        object_path.write_bytes(data)

    register_object(
        object_id=object_id,
        content_hash=content_hash,
        size=len(data),
        storage_path=object_path
    )

    return object_id


def load_object(object_id: str) -> bytes:
    object_path = OBJECTS_DIR / object_id

    if not object_path.exists():
        raise FileNotFoundError("Objeto não encontrado")

    return object_path.read_bytes()
