import json
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
IDENTITY_FILE = CONFIG_DIR / "identity.json"


def generate_node_id():
    return "CLISER-" + uuid.uuid4().hex[:16].upper()


def create_identity():
    node_id = generate_node_id()

    identity = {
        "node_id": node_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "role": "data-node"
    }

    raw = json.dumps(identity, sort_keys=True).encode()
    identity["fingerprint"] = hashlib.sha256(raw).hexdigest()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(IDENTITY_FILE, "w") as f:
        json.dump(identity, f, indent=2)

    return identity


def load_identity():
    if not IDENTITY_FILE.exists():
        return create_identity()

    with open(IDENTITY_FILE, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    identity = load_identity()

    print("=== CLISER DATA NODE ===")
    print(f"Node ID:     {identity['node_id']}")
    print(f"Role:        {identity['role']}")
    print(f"Version:     {identity['version']}")
    print(f"Fingerprint: {identity['fingerprint']}")
