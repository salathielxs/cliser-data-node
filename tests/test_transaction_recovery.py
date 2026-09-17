#!/usr/bin/env python3

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "scripts"),
)

from transaction_recovery_engine import (
    RecoveryAction,
    RecoveryState,
    RecoveryEngine,
    TransactionJournal,
    make_transaction,
)


def new_env():
    temp = tempfile.TemporaryDirectory()

    journal = TransactionJournal(
        Path(temp.name) / "transaction.json"
    )

    return temp, journal


def test_prepared_rollback():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_prepared",
        RecoveryState.PREPARED,
        {"value": 1},
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.ROLLBACK
    assert recovered.state == RecoveryState.ROLLED_BACK.value

    temp.cleanup()


def test_writing_rollback():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_writing",
        RecoveryState.WRITING,
        {"value": 2},
    )

    tx.write_started = True
    tx.write_completed = False

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.ROLLBACK
    assert recovered.state == RecoveryState.ROLLED_BACK.value

    temp.cleanup()


def test_verify_recovery():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_verify",
        RecoveryState.VERIFYING,
        {"value": 3},
    )

    tx.write_completed = True
    tx.verification_started = True
    tx.verification_completed = False

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.REVERIFY
    assert recovered.verification_completed is True
    assert recovered.verification_passed is True

    temp.cleanup()


def test_commit_finalize():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_commit",
        RecoveryState.COMMITTING,
        {"value": 4},
    )

    tx.write_completed = True
    tx.verification_completed = True
    tx.verification_passed = True
    tx.commit_started = True

    journal.save(tx)

    engine = RecoveryEngine(
        journal,
        persisted_state={
            "tx_commit": True,
        },
    )

    recovered, action = engine.recover()

    assert action == RecoveryAction.FINALIZE
    assert recovered.state == RecoveryState.COMMITTED.value
    assert recovered.commit_completed is True

    temp.cleanup()


def test_already_committed():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_done",
        RecoveryState.COMMITTED,
        {"value": 5},
    )

    tx.commit_started = True
    tx.commit_completed = True

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.COMPLETE
    assert recovered.state == RecoveryState.COMMITTED.value

    temp.cleanup()


def test_failed_verification():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_failed",
        RecoveryState.VERIFYING,
        {"value": 6},
    )

    tx.verification_started = True
    tx.verification_completed = True
    tx.verification_passed = False
    tx.error_code = "VERIFICATION_FAILED"

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.ROLLBACK
    assert recovered.state == RecoveryState.ROLLED_BACK.value

    temp.cleanup()


def test_unknown_state_quarantine():

    temp, journal = new_env()

    tx = make_transaction(
        "tx_unknown",
        RecoveryState.IN_DOUBT,
        {"value": 7},
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    recovered, action = engine.recover()

    assert action == RecoveryAction.QUARANTINE
    assert recovered.state == RecoveryState.QUARANTINED.value

    temp.cleanup()


def main():

    tests = [
        test_prepared_rollback,
        test_writing_rollback,
        test_verify_recovery,
        test_commit_finalize,
        test_already_committed,
        test_failed_verification,
        test_unknown_state_quarantine,
    ]

    passed = 0

    for test in tests:

        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1

        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc}")

    print()
    print(f"RESULT: {passed}/{len(tests)}")

    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
