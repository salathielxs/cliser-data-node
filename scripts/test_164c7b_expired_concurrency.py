from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

from node.registry import connect, reserve_replay


PREFIX = "TEST-16.4-C.7-B-CONCURRENCY"
ENVELOPE_ID = PREFIX + "-SAME"


def cleanup():
    conn = connect()
    try:
        conn.execute(
            """
            DELETE FROM replay_records
            WHERE envelope_id = ?
            """,
            (ENVELOPE_ID,),
        )
        conn.commit()
    finally:
        conn.close()


def create_expired_record():
    now = datetime.now(timezone.utc)

    old_received = now - timedelta(seconds=120)
    old_expires = now - timedelta(seconds=60)

    result = reserve_replay(
        envelope_id=ENVELOPE_ID,
        source_peer_id="peer-old",
        source_node_id="node-old",
        received_at=old_received.isoformat(),
        expires_at=old_expires.isoformat(),
    )

    assert result is True


def worker(worker_id):
    now = datetime.now(timezone.utc)

    result = reserve_replay(
        envelope_id=ENVELOPE_ID,
        source_peer_id=f"peer-renew-{worker_id}",
        source_node_id=f"node-renew-{worker_id}",
        received_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=60)).isoformat(),
    )

    return worker_id, result


def get_record():
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT
                envelope_id,
                source_peer_id,
                source_node_id,
                received_at,
                expires_at
            FROM replay_records
            WHERE envelope_id = ?
            """,
            (ENVELOPE_ID,),
        ).fetchone()
    finally:
        conn.close()


def main():
    cleanup()

    print("=" * 70)
    print("16.4-C.7-B — EXPIRED RECORD CONCURRENCY TEST")
    print("=" * 70)

    print()
    print("[1] CREATE EXPIRED RECORD")

    create_expired_record()

    initial = get_record()

    print("initial:", initial)

    assert initial is not None
    print("RESULT: EXPIRED RECORD READY")

    print()
    print("[2] CONCURRENT RENEWAL")

    workers = 8
    results = []

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(worker, worker_id)
            for worker_id in range(1, workers + 1)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    results.sort()

    for result in results:
        print(result)

    successful = sum(
        1 for _, result in results if result is True
    )

    rejected = sum(
        1 for _, result in results if result is False
    )

    print()
    print("[3] CLASSIFICATION")
    print("workers:", workers)
    print("successful renewals:", successful)
    print("rejected renewals:", rejected)

    assert successful == 1
    assert rejected == workers - 1

    print("RESULT: SINGLE WINNER")

    print()
    print("[4] FINAL DATABASE STATE")

    final = get_record()

    print("final:", final)

    assert final is not None
    assert final[0] == ENVELOPE_ID
    assert final[1].startswith("peer-renew-")
    assert final[2].startswith("node-renew-")

    print("RESULT: ONE FINAL RECORD")

    print()
    print("[5] PRIMARY KEY INVARIANT")

    conn = connect()
    try:
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM replay_records
            WHERE envelope_id = ?
            """,
            (ENVELOPE_ID,),
        ).fetchone()[0]
    finally:
        conn.close()

    print("record count:", count)

    assert count == 1

    print("RESULT: PRIMARY KEY INVARIANT PASS")

    print()
    print("[6] CLEANUP")

    cleanup()

    assert get_record() is None

    print("cleanup: PASS")

    print()
    print("=" * 70)
    print("16.4-C.7-B — EXPIRED CONCURRENCY TEST: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()
