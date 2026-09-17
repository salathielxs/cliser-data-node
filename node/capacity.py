import json
import shutil
from pathlib import Path

from node.registry import connect

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
POLICY_FILE = CONFIG_DIR / "storage_policy.json"

STORAGE_DIR = BASE_DIR / "storage"
OBJECTS_DIR = STORAGE_DIR / "objects"
BLOCKS_DIR = STORAGE_DIR / "blocks"
TEMP_DIR = STORAGE_DIR / "temp"
DATA_DIR = BASE_DIR / "data"


DEFAULT_POLICY = {
    "version": "1.0",
    "policy": {
        "reserved_system_bytes": 5 * 1024**3,
        "warning_free_bytes": 5 * 1024**3,
        "critical_free_bytes": 1 * 1024**3,
        "readonly_free_bytes": 512 * 1024**2,
    },
}


def load_policy():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not POLICY_FILE.exists():
        POLICY_FILE.write_text(
            json.dumps(DEFAULT_POLICY, indent=2),
            encoding="utf-8",
        )

    with POLICY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def walk_size(path: Path) -> int:
    if not path.exists():
        return 0

    if path.is_file():
        return path.stat().st_size

    total = 0

    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass

    return total


def filesystem_capacity():
    total, used, free = shutil.disk_usage(BASE_DIR)

    utilization = (used / total * 100) if total else 0

    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "utilization_percent": round(utilization, 2),
    }


def registry_capacity():
    conn = connect()

    direct = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
          AND storage_path IS NOT NULL
    """).fetchone()

    block_objects = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM objects
        WHERE status = 'ACTIVE'
          AND storage_path IS NULL
    """).fetchone()

    manifests = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(total_size), 0)
        FROM manifests
        WHERE status = 'ACTIVE'
    """).fetchone()

    blocks = conn.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(size), 0)
        FROM blocks
        WHERE status = 'ACTIVE'
    """).fetchone()

    conn.close()

    return {
        "direct_objects": direct[0],
        "direct_logical_bytes": direct[1],

        "block_objects": block_objects[0],
        "block_logical_bytes": block_objects[1],

        "manifests": manifests[0],
        "manifest_logical_bytes": manifests[1],

        "blocks": blocks[0],
        "block_physical_bytes": blocks[1],
    }


def storage_capacity():
    filesystem = filesystem_capacity()
    registry = registry_capacity()
    policy = load_policy()["policy"]

    logical_direct = registry["direct_logical_bytes"]
    logical_blocked = registry["block_logical_bytes"]

    logical_payload = logical_direct + logical_blocked

    physical_direct = walk_size(OBJECTS_DIR)
    physical_blocks = walk_size(BLOCKS_DIR)

    physical_payload = physical_direct + physical_blocks

    metadata_bytes = walk_size(DATA_DIR)
    temporary_bytes = walk_size(TEMP_DIR)

    cliser_physical_bytes = (
        physical_payload
        + metadata_bytes
        + temporary_bytes
    )

    savings_bytes = max(
        logical_payload - physical_payload,
        0,
    )

    dedup_ratio = (
        logical_payload / physical_payload
        if physical_payload
        else 1.0
    )

    savings_percent = (
        savings_bytes / logical_payload * 100
        if logical_payload
        else 0
    )

    reserved = policy["reserved_system_bytes"]

    # Espaço do dispositivo que o CLISER não deve consumir.
    cliser_capacity = max(
        filesystem["total_bytes"] - reserved,
        0,
    )

    cliser_used = cliser_physical_bytes

    cliser_free = max(
        cliser_capacity - cliser_used,
        0,
    )

    if cliser_free <= policy["readonly_free_bytes"]:
        state = "READ_ONLY"

    elif cliser_free <= policy["critical_free_bytes"]:
        state = "CRITICAL"

    elif cliser_free <= policy["warning_free_bytes"]:
        state = "WARNING"

    else:
        state = "NORMAL"

    return {
        "filesystem": filesystem,

        "registry": registry,

        "logical": {
            "direct_bytes": logical_direct,
            "block_managed_bytes": logical_blocked,
            "payload_bytes": logical_payload,
        },

        "physical": {
            "direct_object_bytes": physical_direct,
            "block_bytes": physical_blocks,
            "payload_bytes": physical_payload,
            "metadata_bytes": metadata_bytes,
            "temporary_bytes": temporary_bytes,
            "cliser_bytes": cliser_physical_bytes,
        },

        "cliser_capacity": {
            "reserved_system_bytes": reserved,
            "capacity_bytes": cliser_capacity,
            "used_bytes": cliser_used,
            "free_bytes": cliser_free,
            "utilization_percent": round(
                (
                    cliser_used / cliser_capacity * 100
                )
                if cliser_capacity
                else 0,
                4,
            ),
            "state": state,
        },

        "policy": policy,

        "deduplication": {
            "logical_bytes": logical_payload,
            "physical_payload_bytes": physical_payload,
            "savings_bytes": savings_bytes,
            "ratio": round(dedup_ratio, 4),
            "savings_percent": round(
                savings_percent,
                2,
            ),
        },
    }


def format_bytes(value):
    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
        "PB",
    ]

    value = float(value)

    for unit in units:
        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} EB"


def capacity_report():
    data = storage_capacity()

    fs = data["filesystem"]
    reg = data["registry"]
    logical = data["logical"]
    physical = data["physical"]
    cliser = data["cliser_capacity"]
    dedup = data["deduplication"]

    print("=== CLISER DATA NODE CAPACITY ===")

    print()
    print("DEVICE")
    print("Total:", format_bytes(fs["total_bytes"]))
    print("Used: ", format_bytes(fs["used_bytes"]))
    print("Free: ", format_bytes(fs["free_bytes"]))
    print("Usage:", f'{fs["utilization_percent"]}%')

    print()
    print("REGISTRY")
    print("Direct objects:", reg["direct_objects"])
    print("Manifests:     ", reg["manifests"])
    print("Blocks:        ", reg["blocks"])

    print()
    print("LOGICAL PAYLOAD")
    print(
        "Direct objects: ",
        format_bytes(logical["direct_bytes"]),
    )
    print(
        "Block-managed:  ",
        format_bytes(logical["block_managed_bytes"]),
    )
    print(
        "Total payload:  ",
        format_bytes(logical["payload_bytes"]),
    )

    print()
    print("PHYSICAL STORAGE")
    print(
        "Direct objects: ",
        format_bytes(physical["direct_object_bytes"]),
    )
    print(
        "Blocks:         ",
        format_bytes(physical["block_bytes"]),
    )
    print(
        "Payload:        ",
        format_bytes(physical["payload_bytes"]),
    )
    print(
        "Metadata:       ",
        format_bytes(physical["metadata_bytes"]),
    )
    print(
        "Temporary:      ",
        format_bytes(physical["temporary_bytes"]),
    )
    print(
        "CLISER total:   ",
        format_bytes(physical["cliser_bytes"]),
    )

    print()
    print("CLISER CAPACITY")
    print(
        "Reserved system:",
        format_bytes(cliser["reserved_system_bytes"]),
    )
    print(
        "CLISER capacity:",
        format_bytes(cliser["capacity_bytes"]),
    )
    print(
        "CLISER used:    ",
        format_bytes(cliser["used_bytes"]),
    )
    print(
        "CLISER free:    ",
        format_bytes(cliser["free_bytes"]),
    )
    print(
        "CLISER usage:   ",
        f'{cliser["utilization_percent"]}%',
    )
    print(
        "Policy state:   ",
        cliser["state"],
    )

    print()
    print("DEDUPLICATION")
    print(
        "Logical:        ",
        format_bytes(dedup["logical_bytes"]),
    )
    print(
        "Physical:       ",
        format_bytes(dedup["physical_payload_bytes"]),
    )
    print(
        "Savings:        ",
        format_bytes(dedup["savings_bytes"]),
    )
    print(
        "Savings:        ",
        f'{dedup["savings_percent"]}%',
    )
    print(
        "Ratio:          ",
        f'{dedup["ratio"]}x',
    )

    return data


def allocation_capacity():
    data = storage_capacity()

    fs = data["filesystem"]
    policy = data["policy"]

    reserved = policy["reserved_system_bytes"]
    readonly_floor = policy["readonly_free_bytes"]
    safety = policy["filesystem_safety_bytes"]

    device_free = fs["free_bytes"]

    usable_free = max(
        device_free
        - reserved
        - readonly_floor
        - safety,
        0,
    )

    return {
        "device_free_bytes": device_free,
        "reserved_system_bytes": reserved,
        "readonly_floor_bytes": readonly_floor,
        "filesystem_safety_bytes": safety,
        "usable_free_bytes": usable_free,
        "policy_state": data["cliser_capacity"]["state"],
    }


def estimate_allocation(required_bytes: int):
    if required_bytes < 0:
        raise ValueError("required_bytes não pode ser negativo.")

    policy = load_policy()["policy"]

    block_size = 1024 * 1024

    block_count = (
        (required_bytes + block_size - 1)
        // block_size
        if required_bytes
        else 0
    )

    object_metadata = (
        policy["metadata_overhead_per_object_bytes"]
    )

    block_metadata = (
        block_count
        * policy["metadata_overhead_per_block_bytes"]
    )

    estimated_overhead = (
        object_metadata
        + block_metadata
    )

    estimated_physical = (
        required_bytes
        + estimated_overhead
    )

    return {
        "payload_bytes": required_bytes,
        "block_count": block_count,
        "object_metadata_bytes": object_metadata,
        "block_metadata_bytes": block_metadata,
        "estimated_overhead_bytes": estimated_overhead,
        "estimated_physical_bytes": estimated_physical,
    }


def can_allocate(required_bytes: int):
    allocation = allocation_capacity()
    estimate = estimate_allocation(required_bytes)

    usable_free = allocation["usable_free_bytes"]
    required_physical = estimate["estimated_physical_bytes"]

    if allocation["policy_state"] == "READ_ONLY":
        return {
            "allowed": False,
            "reason": "READ_ONLY",
            "estimate": estimate,
            "capacity": allocation,
        }

    if required_physical > usable_free:
        return {
            "allowed": False,
            "reason": "INSUFFICIENT_CAPACITY",
            "estimate": estimate,
            "capacity": allocation,
        }

    return {
        "allowed": True,
        "reason": "CAPACITY_AVAILABLE",
        "estimate": estimate,
        "capacity": allocation,
    }


def capacity_check(required_bytes: int):
    result = can_allocate(required_bytes)

    print("=== CAPACITY CHECK ===")
    print("Required:", format_bytes(result["required_bytes"]))
    print(
        "Device free:",
        format_bytes(result["device_free_bytes"])
    )
    print(
        "Usable free:",
        format_bytes(result["usable_free_bytes"])
    )
    print("State:", result["state"])
    print("Allowed:", result["allowed"])
    print("Reason:", result["reason"])

    return result


if __name__ == "__main__":
    capacity_report()
