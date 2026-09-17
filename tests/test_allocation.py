from node.allocation import (
    estimate_allocation,
    check_allocation_capacity,
)


def test_small_allocation():
    data = b"CLISER" * 100

    allocation = estimate_allocation(
        data,
        block_mode=True,
    )

    result = check_allocation_capacity(
        allocation
    )

    assert result["allowed"] is True
    assert result["state"] == "ALLOW"

    print("SMALL ALLOCATION: OK")


def test_metadata_accounting():
    data = b"A" * 2100

    allocation = estimate_allocation(
        data,
        block_mode=True,
    )

    assert allocation["physical_payload_delta"] == 2100
    assert allocation["object_metadata_bytes"] == 4096
    assert allocation["block_metadata_bytes"] == 512
    assert allocation["metadata_overhead_bytes"] == 4608
    assert allocation["filesystem_safety_bytes"] == 67108864

    expected = (
        2100
        + 4096
        + 512
        + 67108864
    )

    assert allocation["required_physical_bytes"] == expected

    print("METADATA ACCOUNTING: OK")


def test_capacity_deny():
    allocation = {
        "physical_payload_delta": 1,
        "metadata_overhead_bytes": 0,
        "filesystem_safety_bytes": 0,
        "required_physical_bytes": 10**30,
    }

    result = check_allocation_capacity(
        allocation
    )

    assert result["allowed"] is False
    assert result["state"] == "DENY"

    print("CAPACITY DENY: OK")


if __name__ == "__main__":
    print("=" * 60)
    print("ALLOCATION / CAPACITY TEST")
    print("=" * 60)

    test_small_allocation()
    test_metadata_accounting()
    test_capacity_deny()

    print("=" * 60)
    print("ALLOCATION / CAPACITY: OK")
    print("=" * 60)
