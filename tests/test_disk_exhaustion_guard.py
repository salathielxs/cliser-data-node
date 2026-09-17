from node import capacity


def test_normal_capacity_allows_allocation(monkeypatch):
    monkeypatch.setattr(
        capacity,
        "allocation_capacity",
        lambda: {
            "device_free_bytes": 10 * 1024**3,
            "reserved_system_bytes": 5 * 1024**3,
            "readonly_floor_bytes": 512 * 1024**2,
            "filesystem_safety_bytes": 64 * 1024**2,
            "usable_free_bytes": 4 * 1024**3,
            "policy_state": "NORMAL",
        },
    )

    result = capacity.can_allocate(1024)

    assert result["allowed"] is True
    assert result["reason"] == "CAPACITY_AVAILABLE"


def test_insufficient_capacity_denies_allocation(monkeypatch):
    monkeypatch.setattr(
        capacity,
        "allocation_capacity",
        lambda: {
            "device_free_bytes": 6 * 1024**3,
            "reserved_system_bytes": 5 * 1024**3,
            "readonly_floor_bytes": 512 * 1024**2,
            "filesystem_safety_bytes": 64 * 1024**2,
            "usable_free_bytes": 1024,
            "policy_state": "CRITICAL",
        },
    )

    result = capacity.can_allocate(4096)

    assert result["allowed"] is False
    assert result["reason"] == "INSUFFICIENT_CAPACITY"


def test_read_only_denies_allocation(monkeypatch):
    monkeypatch.setattr(
        capacity,
        "allocation_capacity",
        lambda: {
            "device_free_bytes": 512 * 1024**2,
            "reserved_system_bytes": 5 * 1024**3,
            "readonly_floor_bytes": 512 * 1024**2,
            "filesystem_safety_bytes": 64 * 1024**2,
            "usable_free_bytes": 0,
            "policy_state": "READ_ONLY",
        },
    )

    result = capacity.can_allocate(1)

    assert result["allowed"] is False
    assert result["reason"] == "READ_ONLY"
