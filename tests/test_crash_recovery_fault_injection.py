#!/usr/bin/env python3

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "scripts"),
)

from crash_recovery_fault_injection import (
    FaultPoint,
    Journal,
    FaultInjector,
    TransactionProcessor,
    RecoveryEngine,
    State,
)


def run_case(fault):

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    processor = TransactionProcessor(
        journal,
        FaultInjector(fault),
    )

    tx = processor.create(
        "tx_test",
        {
            "value": 123,
        },
    )

    crashed = False

    try:

        processor.execute(tx)

    except RuntimeError as exc:

        assert str(exc).startswith(
            "INJECTED_CRASH:"
        )

        crashed = True

    recovered, action = RecoveryEngine(
        journal
    ).recover()

    temp.cleanup()

    return crashed, recovered, action


def test_after_prepared():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_PREPARED
    )

    assert crashed
    assert action.value == "ROLLBACK"
    assert tx.state == State.ROLLED_BACK.value


def test_during_write():

    crashed, tx, action = run_case(
        FaultPoint.DURING_WRITE
    )

    assert crashed
    assert action.value == "ROLLBACK"
    assert tx.state == State.ROLLED_BACK.value


def test_after_write():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_WRITE
    )

    assert crashed
    assert action.value == "REVERIFY"
    assert tx.state == State.COMMITTED.value


def test_during_verify():

    crashed, tx, action = run_case(
        FaultPoint.DURING_VERIFY
    )

    assert crashed
    assert action.value == "REVERIFY"
    assert tx.state == State.COMMITTED.value


def test_after_verify():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_VERIFY
    )

    assert crashed
    assert action.value == "RECOVER"
    assert tx.state == State.COMMITTED.value


def test_during_commit():

    crashed, tx, action = run_case(
        FaultPoint.DURING_COMMIT
    )

    assert crashed
    assert action.value == "RECOVER"
    assert tx.state == State.COMMITTED.value


def test_after_commit():

    crashed, tx, action = run_case(
        FaultPoint.AFTER_COMMIT
    )

    assert crashed
    assert action.value == "FINALIZE"
    assert tx.state == State.COMMITTED.value


def test_no_fault():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    processor = TransactionProcessor(
        journal
    )

    tx = processor.create(
        "tx_no_fault",
        {
            "value": 999,
        },
    )

    result = processor.execute(tx)

    assert result.state == State.COMMITTED.value
    assert result.commit_completed
    assert result.persisted

    temp.cleanup()


def main():

    tests = [
        test_after_prepared,
        test_during_write,
        test_after_write,
        test_during_verify,
        test_after_verify,
        test_during_commit,
        test_after_commit,
        test_no_fault,
    ]

    passed = 0

    for test in tests:

        try:

            test()

            print(
                f"[PASS] {test.__name__}"
            )

            passed += 1

        except Exception as exc:

            print(
                f"[FAIL] "
                f"{test.__name__}: {exc}"
            )

    print()
    print(
        f"RESULT: {passed}/{len(tests)}"
    )

    if passed != len(tests):

        raise SystemExit(1)


if __name__ == "__main__":

    main()
