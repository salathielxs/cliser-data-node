import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from node import registry
from node import namespace_manager
from node.storage import OBJECTS_DIR
from node.recovery import (
    recover_transaction,
    recover_pending_transactions,
)


TEST_NS = "commit_marker_test"
TX_ID = "tx-commit-marker-test"
OBJECT_ID = "object-commit-marker-test"
TEST_DATA = b"CLISER-COMMIT-MARKER-TEST"
TEST_OBJECT_PATH = OBJECTS_DIR / OBJECT_ID


def cleanup():
    try:
        if TEST_OBJECT_PATH.exists():
            TEST_OBJECT_PATH.unlink()
    except Exception:
        pass

    conn = registry.connect()

    conn.execute(
        "DELETE FROM transaction_journal WHERE transaction_id = ?",
        (TX_ID,),
    )

    conn.execute(
        "DELETE FROM transactions WHERE transaction_id = ?",
        (TX_ID,),
    )

    conn.execute(
        "DELETE FROM objects WHERE object_id = ?",
        (OBJECT_ID,),
    )

    conn.execute(
        "DELETE FROM manifests WHERE object_id = ?",
        (OBJECT_ID,),
    )

    conn.execute(
        "DELETE FROM manifest_blocks WHERE object_id = ?",
        (OBJECT_ID,),
    )

    conn.commit()
    conn.close()


def ensure_namespace():
    if not namespace_manager.namespace_exists(TEST_NS):
        from node.namespace_manager import create_namespace

        create_namespace(
            TEST_NS,
            quota_bytes=0,
        )

    from datetime import datetime, timezone

    registry.register_quota(
        TEST_NS,
        0,
        datetime.now(timezone.utc).isoformat(),
    )


def main():
    print("\nCLISER DATA NODE — COMMIT MARKER TEST")
    print("=" * 50)

    cleanup()
    ensure_namespace()

    # ---------------------------------------------------------
    # Criar transação interrompida exatamente em COMMITTING.
    # ---------------------------------------------------------

    content_hash = __import__("hashlib").sha256(
        TEST_DATA
    ).hexdigest()

    OBJECTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    TEST_OBJECT_PATH.write_bytes(TEST_DATA)

    registry.register_object(
        object_id=OBJECT_ID,
        content_hash=content_hash,
        size=len(TEST_DATA),
        storage_path=TEST_OBJECT_PATH,
        namespace=TEST_NS,
    )

    registry.create_transaction(
        transaction_id=TX_ID,
        object_id=OBJECT_ID,
        namespace=TEST_NS,
        operation="PUT",
        state="COMMITTING",
        metadata={
            "test": "commit_marker_recovery",
        },
    )

    registry.create_transaction_journal(
        transaction_id=TX_ID,
        phase="COMMIT_MARKER",
        resources={
            "object_id": OBJECT_ID,
            "namespace": TEST_NS,
            "test": True,
        },
        verified=True,
    )

    registry.update_transaction_journal(
        TX_ID,
        phase="COMMIT_MARKER",
        verified=True,
        commit_marker=True,
    )

    tx_before = registry.get_transaction(TX_ID)
    journal_before = registry.get_transaction_journal(TX_ID)

    assert tx_before["state"] == "COMMITTING"
    assert journal_before["commit_marker"] is True

    print("COMMITTING + MARKER: OK")

    # ---------------------------------------------------------
    # Recovery
    # ---------------------------------------------------------

    result = recover_transaction(TX_ID)

    assert result["previous_state"] == "COMMITTING"
    assert result["final_state"] == "COMMITTED"
    assert result["action"] == "COMMIT"
    assert result["recovered"] is True

    tx_after = registry.get_transaction(TX_ID)

    assert tx_after["state"] == "COMMITTED"
    assert tx_after["error"] is None

    print("RECOVERY → COMMITTED: OK")
    print("COMMIT FINALIZED: OK")

    # ---------------------------------------------------------
    # Segunda recuperação: deve ser NOOP.
    # ---------------------------------------------------------

    result2 = recover_transaction(TX_ID)

    assert result2["previous_state"] == "COMMITTED"
    assert result2["final_state"] == "COMMITTED"
    assert result2["action"] == "NOOP"
    assert result2["recovered"] is False

    print("SECOND RECOVERY: NOOP OK")
    print("IDEMPOTENCY: OK")

    # ---------------------------------------------------------
    # Recovery global também não deve tocar na transação.
    # ---------------------------------------------------------

    pending = recover_pending_transactions()

    assert pending["errors"] == 0

    tx_final = registry.get_transaction(TX_ID)

    assert tx_final["state"] == "COMMITTED"

    print("GLOBAL RECOVERY: OK")
    print("COMMITTED PRESERVED: OK")

    cleanup()

    print("\n" + "=" * 50)
    print("COMMIT MARKER: PASS")
    print("FASE 12.1 — COMMIT RECOVERY VALIDADO")
    print("=" * 50)


if __name__ == "__main__":
    main()
