import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
ENGINE = SCRIPTS / "crash_recovery_fault_injection.py"


def run_process(code, journal_path):
    env = dict()
    import os
    env.update(os.environ)

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )

    return result


def produce(journal_path, tx_id, value, fault):
    script = f'''
import sys
sys.path.insert(0, {str(SCRIPTS)!r})

from crash_recovery_fault_injection import (
    TransactionProcessor,
    Journal,
    FaultInjector,
    FaultPoint,
)

journal = Journal({str(journal_path)!r})
injector = FaultInjector(FaultPoint.{fault})
processor = TransactionProcessor(journal, injector)

tx = processor.create(
    transaction_id={tx_id!r},
    payload={{"value": {value!r}}},
)

processor.execute(tx)
'''

    return run_process(script, journal_path)


def recover(journal_path):
    script = f'''
import sys
sys.path.insert(0, {str(SCRIPTS)!r})

from crash_recovery_fault_injection import (
    Journal,
    RecoveryEngine,
)

journal = Journal({str(journal_path)!r})
engine = RecoveryEngine(journal)

tx, action = engine.recover()

print("STATE=" + tx.state)
print("ACTION=" + action.value)
print("TRANSACTION_ID=" + tx.transaction_id)
print("IDEMPOTENCY_KEY=" + tx.idempotency_key)
print("PAYLOAD_HASH=" + tx.payload_hash)
print("RESULT_HASH=" + str(tx.result_hash))
print("RECOVERY_COUNT=" + str(tx.recovery_count))
print("COMMIT_COMPLETED=" + str(tx.commit_completed))
'''

    return run_process(script, journal_path)


def assert_expected_crash(result, fault):
    assert result.returncode != 0, (
        "Fault injection did not terminate the producer process"
    )

    assert f"INJECTED_CRASH:{fault}" in result.stderr, (
        f"Expected injected crash {fault!r} not found in stderr"
    )


def parse_output(output):
    data = {}

    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            data[key] = value

    return data


def test_journal_survives_process_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_001",
            123,
            "AFTER_PREPARED",
        )

        assert_expected_crash(result, "AFTER_PREPARED")

        assert path.exists(), (
            "Journal was not persisted before the injected crash"
        )

        data = json.loads(path.read_text())

        assert data["transaction_id"] == "tx_restart_001"
        assert data["state"] == "PREPARED"
        assert data["idempotency_key"] == "idem_tx_restart_001"
        assert data["payload_hash"]


def test_restart_prepared():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_002",
            456,
            "AFTER_PREPARED",
        )

        assert_expected_crash(result, "AFTER_PREPARED")
        assert path.exists()

        result = recover(path)

        assert result.returncode == 0, result.stderr

        data = parse_output(result.stdout)

        assert data["STATE"] == "ROLLED_BACK"
        assert data["ACTION"] == "ROLLBACK"
        assert data["TRANSACTION_ID"] == "tx_restart_002"


def test_restart_after_write():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_003",
            789,
            "AFTER_WRITE",
        )

        assert_expected_crash(result, "AFTER_WRITE")
        assert path.exists()

        result = recover(path)

        assert result.returncode == 0, result.stderr

        data = parse_output(result.stdout)

        assert data["STATE"] == "COMMITTED"
        assert data["ACTION"] == "REVERIFY"
        assert data["TRANSACTION_ID"] == "tx_restart_003"
        assert data["RESULT_HASH"] not in ("", "None")


def test_restart_after_verify():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_004",
            999,
            "AFTER_VERIFY",
        )

        assert_expected_crash(result, "AFTER_VERIFY")
        assert path.exists()

        result = recover(path)

        assert result.returncode == 0, result.stderr

        data = parse_output(result.stdout)

        assert data["STATE"] == "COMMITTED"
        assert data["ACTION"] == "RECOVER"
        assert data["TRANSACTION_ID"] == "tx_restart_004"
        assert data["RESULT_HASH"] not in ("", "None")


def test_restart_after_commit_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_005",
            111,
            "AFTER_COMMIT",
        )

        assert_expected_crash(result, "AFTER_COMMIT")
        assert path.exists()

        first = recover(path)

        assert first.returncode == 0, first.stderr

        first_data = parse_output(first.stdout)

        assert first_data["STATE"] == "COMMITTED"
        assert first_data["ACTION"] == "FINALIZE"
        assert first_data["RESULT_HASH"] not in ("", "None")
        assert first_data["COMMIT_COMPLETED"] == "True"

        result_hash_1 = first_data["RESULT_HASH"]
        transaction_id_1 = first_data["TRANSACTION_ID"]

        second = recover(path)

        assert second.returncode == 0, second.stderr

        second_data = parse_output(second.stdout)

        assert second_data["STATE"] == "COMMITTED"
        assert second_data["TRANSACTION_ID"] == transaction_id_1
        assert second_data["RESULT_HASH"] == result_hash_1


def test_identity_survives_restart():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_006",
            222,
            "AFTER_VERIFY",
        )

        assert_expected_crash(result, "AFTER_VERIFY")
        assert path.exists()

        before = json.loads(path.read_text())

        result = recover(path)

        assert result.returncode == 0, result.stderr

        after = json.loads(path.read_text())

        assert after["transaction_id"] == before["transaction_id"]
        assert after["idempotency_key"] == before["idempotency_key"]
        assert after["payload_hash"] == before["payload_hash"]


def test_atomic_journal_json():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "transaction.json"

        result = produce(
            path,
            "tx_restart_007",
            333,
            "AFTER_PREPARED",
        )

        assert_expected_crash(result, "AFTER_PREPARED")
        assert path.exists()

        raw = path.read_text(encoding="utf-8")

        data = json.loads(raw)

        assert isinstance(data, dict)
        assert data["transaction_id"] == "tx_restart_007"
        assert data["state"] == "PREPARED"


def main():
    tests = [
        test_journal_survives_process_restart,
        test_restart_prepared,
        test_restart_after_write,
        test_restart_after_verify,
        test_restart_after_commit_idempotent,
        test_identity_survives_restart,
        test_atomic_journal_json,
    ]

    passed = 0

    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
            passed += 1
        except Exception as exc:
            print(f"[FAIL] {test.__name__}: {exc!r}")

    print()
    print(f"RESULT: {passed}/{len(tests)}")

    if passed == len(tests):
        print("STATUS: PASS")
        return 0

    print("STATUS: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
