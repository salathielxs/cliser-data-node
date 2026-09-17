from node.transaction import Transaction, TransactionState


def test_transaction_failure_can_rollback():
    tx = Transaction("reliability-test-rollback")

    assert tx.state == TransactionState.PREPARED

    tx.transition(TransactionState.WRITING)
    assert tx.state == TransactionState.WRITING

    tx.fail("SIMULATED_DATABASE_FAILURE")

    assert tx.state == TransactionState.FAILED
    assert tx.error == "SIMULATED_DATABASE_FAILURE"

    tx.rollback()

    assert tx.state == TransactionState.ROLLBACK


def test_failed_transaction_cannot_commit_directly():
    tx = Transaction("reliability-test-no-direct-commit")

    tx.transition(TransactionState.WRITING)
    tx.fail("SIMULATED_FAILURE")

    assert tx.state == TransactionState.FAILED

    try:
        tx.commit()
    except ValueError as exc:
        assert "COMMITTING" in str(exc)
    else:
        raise AssertionError(
            "Transação FAILED não deveria permitir COMMIT direto."
        )


def test_rollback_requires_failed_state():
    tx = Transaction("reliability-test-invalid-rollback")

    assert tx.state == TransactionState.PREPARED

    try:
        tx.rollback()
    except ValueError as exc:
        assert "FAILED" in str(exc)
    else:
        raise AssertionError(
            "Rollback deveria exigir estado FAILED."
        )
