#!/usr/bin/env python3

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "scripts"),
)

from recovery_idempotency import (
    Journal,
    RecoveryEngine,
    RecoveryAction,
    State,
    Transaction,
    create_committed_transaction,
    create_rollback_transaction,
)


def test_committed_recovery_is_idempotent():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = create_committed_transaction()

    original_result_hash = tx.result_hash
    original_idempotency_key = tx.idempotency_key

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.COMPLETE
    assert tx1.state == State.COMMITTED.value
    assert tx1.commit_count == 1
    assert tx1.result_hash == original_result_hash
    assert tx1.idempotency_key == original_idempotency_key

    tx2, action2 = engine.recover()

    assert action2 == RecoveryAction.COMPLETE
    assert tx2.state == State.COMMITTED.value
    assert tx2.commit_count == 1
    assert tx2.result_hash == original_result_hash

    tx3, action3 = engine.recover()

    assert action3 == RecoveryAction.COMPLETE
    assert tx3.state == State.COMMITTED.value
    assert tx3.commit_count == 1
    assert tx3.recovery_count == 3

    temp.cleanup()


def test_finalize_is_exactly_once():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = Transaction(
        transaction_id="tx-finalize-001",
        idempotency_key="idem-finalize-001",
        state=State.COMMITTING.value,
        payload_hash="payload-hash",
        result_hash="result-hash",
        commit_started=True,
        commit_completed=False,
        persisted=True,
        commit_count=0,
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.FINALIZE
    assert tx1.state == State.COMMITTED.value
    assert tx1.commit_completed is True
    assert tx1.commit_count == 1

    tx2, action2 = engine.recover()

    assert action2 == RecoveryAction.COMPLETE
    assert tx2.state == State.COMMITTED.value
    assert tx2.commit_count == 1

    tx3, action3 = engine.recover()

    assert action3 == RecoveryAction.COMPLETE
    assert tx3.commit_count == 1

    temp.cleanup()


def test_rollback_is_terminal():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = create_rollback_transaction()

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.QUARANTINE
    assert tx1.state == State.QUARANTINED.value
    assert tx1.commit_count == 0

    temp.cleanup()


def test_no_duplicate_commit_from_recover():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = Transaction(
        transaction_id="tx-duplicate-001",
        idempotency_key="idem-duplicate-001",
        state=State.WRITING.value,
        payload_hash="payload",
        result_hash="result",
        write_started=True,
        write_completed=True,
        verification_completed=False,
        verification_passed=False,
        commit_started=False,
        commit_completed=False,
        persisted=False,
        commit_count=0,
    )

    journal.save(tx)

    engine = RecoveryEngine(journal)

    tx1, action1 = engine.recover()

    assert action1 == RecoveryAction.REVERIFY
    assert tx1.state == State.COMMITTED.value
    assert tx1.commit_count == 1

    tx2, action2 = engine.recover()

    assert action2 == RecoveryAction.COMPLETE
    assert tx2.state == State.COMMITTED.value
    assert tx2.commit_count == 1

    tx3, action3 = engine.recover()

    assert action3 == RecoveryAction.COMPLETE
    assert tx3.state == State.COMMITTED.value
    assert tx3.commit_count == 1

    temp.cleanup()


def test_identity_and_result_are_stable():

    temp = tempfile.TemporaryDirectory()

    journal = Journal(
        Path(temp.name) / "transaction.json"
    )

    tx = create_committed_transaction()

    transaction_id = tx.transaction_id
    idempotency_key = tx.idempotency_key
    result_hash = tx.result_hash

    journal.save(tx)

    engine = RecoveryEngine(journal)

    for _ in range(5):

        recovered, action = engine.recover()

        assert recovered.transaction_id == transaction_id
        assert recovered.idempotency_key == idempotency_key
        assert recovered.result_hash == result_hash
        assert recovered.commit_count == 1
        assert recovered.state == State.COMMITTED.value
        assert action == RecoveryAction.COMPLETE

    temp.cleanup()


def run_test(name, fn):

    try:
        fn()
        print(f"[PASS] {name}")
        return True

    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def main():

    tests = [
        (
            "test_committed_recovery_is_idempotent",
            test_committed_recovery_is_idempotent,
        ),
        (
            "test_finalize_is_exactly_once",
            test_finalize_is_exactly_once,
        ),
        (
            "test_rollback_is_terminal",
            test_rollback_is_terminal,
        ),
        (
            "test_no_duplicate_commit_from_recover",
            test_no_duplicate_commit_from_recover,
        ),
        (
            "test_identity_and_result_are_stable",
            test_identity_and_result_are_stable,
        ),
    ]

    passed = 0

    for name, fn in tests:

        if run_test(name, fn):
            passed += 1

    total = len(tests)

    print()
    print(f"RESULT: {passed}/{total}")

    if passed == total:
        print("STATUS: PASS")
        return 0

    print("STATUS: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
