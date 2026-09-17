from node.health import run_health
from node.metrics import storage_metrics


print("=" * 60)
print("CLISER DATA NODE — HEALTH + METRICS TEST")
print("=" * 60)


health = run_health()

print()
print("HEALTH STATUS:", health["status"])

for name, result in health["checks"].items():
    print(
        f"{name.upper():15} "
        f"{result['status']}"
    )

assert health["status"] in {
    "HEALTHY",
    "WARNING",
}

assert health["checks"]["identity"]["status"] == "OK"
assert health["checks"]["registry"]["status"] == "OK"
assert health["checks"]["namespaces"]["status"] == "OK"
assert health["checks"]["objects"]["status"] == "OK"
assert health["checks"]["blocks"]["status"] == "OK"
assert health["checks"]["manifests"]["status"] == "OK"
assert health["checks"]["transactions"]["status"] in {
    "OK",
    "WARNING",
}
assert health["checks"]["journal"]["status"] in {
    "OK",
    "WARNING",
}
assert health["checks"]["integrity"]["status"] == "OK"
assert health["checks"]["capacity"]["status"] in {
    "OK",
    "WARNING",
}


metrics = storage_metrics()

print()
print("METRICS")
print("-" * 60)

print(
    "Objects:",
    metrics["objects"]
)

print(
    "Direct:",
    metrics["direct"]
)

print(
    "Block objects:",
    metrics["block_objects"]
)

print(
    "Blocks:",
    metrics["blocks"]
)

print(
    "Deduplication:",
    metrics["deduplication"]
)

assert "objects" in metrics
assert "direct" in metrics
assert "block_objects" in metrics
assert "blocks" in metrics
assert "deduplication" in metrics
assert "capacity" in metrics

assert metrics["objects"]["total"] >= 0
assert metrics["objects"]["logical_bytes"] >= 0
assert metrics["blocks"]["unique"] >= 0
assert metrics["blocks"]["physical_bytes"] >= 0
assert metrics["deduplication"]["ratio"] >= 1.0

print()
print("=" * 60)
print("HEALTH + METRICS: OK")
print("=" * 60)
