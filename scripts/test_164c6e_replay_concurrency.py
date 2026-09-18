from multiprocessing import Process, Queue
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from node.registry import reserve_replay, connect


def cleanup(envelope_id):
    conn = connect()
    try:
        conn.execute(
            """
            DELETE FROM replay_records
            WHERE envelope_id = ?
            """,
            (envelope_id,),
        )
        conn.commit()
    finally:
        conn.close()


def worker(envelope_id, queue, worker_id):
    try:
        now = datetime.now(timezone.utc)

        result = reserve_replay(
            envelope_id=envelope_id,
            source_peer_id=f"peer-concurrency-{worker_id}",
            source_node_id=f"node-concurrency-{worker_id}",
            received_at=now.isoformat(),
            expires_at=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )

        queue.put(
            (
                worker_id,
                "SUCCESS",
                result,
            )
        )

    except Exception as exc:
        queue.put(
            (
                worker_id,
                "ERROR",
                type(exc).__name__,
                str(exc),
            )
        )


def main():
    print("=" * 70)
    print("16.4-C.6-E — REPLAY CONCURRENCY FORENSIC")
    print("=" * 70)

    envelope_id = (
        "TEST-16.4-C.6-E-"
        + uuid4().hex
    )

    queue = Queue()

    processes = [
        Process(
            target=worker,
            args=(envelope_id, queue, i),
        )
        for i in range(1, 9)
    ]

    try:
        print("\n[1] STARTING 8 CONCURRENT RESERVATIONS")

        for process in processes:
            process.start()

        results = []

        for _ in processes:
            results.append(queue.get())

        for process in processes:
            process.join()

        results.sort(key=lambda item: item[0])

        print("\n[2] RESULTS")

        for result in results:
            print(result)

        successes = [
            result
            for result in results
            if len(result) >= 3
            and result[1] == "SUCCESS"
            and result[2] is True
        ]

        false_results = [
            result
            for result in results
            if len(result) >= 3
            and result[1] == "SUCCESS"
            and result[2] is False
        ]

        errors = [
            result
            for result in results
            if result[1] == "ERROR"
        ]

        print("\n[3] CLASSIFICATION")

        print("successful reservations:", len(successes))
        print("rejected reservations:", len(false_results))
        print("errors:", len(errors))

        print("\n[4] DATABASE STATE")

        conn = connect()

        try:
            rows = conn.execute(
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
                (envelope_id,),
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            print(row)

        print("\n[5] ATOMICITY OBSERVATION")

        if len(successes) == 1 and len(rows) == 1:
            print(
                "RESULT: SINGLE RESERVATION OBSERVED"
            )
        elif len(successes) == 0:
            print(
                "RESULT: NO RESERVATION SUCCEEDED"
            )
        else:
            print(
                "RESULT: MULTIPLE RESERVATIONS OBSERVED"
            )

        print("\n" + "=" * 70)
        print("16.4-C.6-E — FORENSIC OBSERVATION COMPLETE")
        print("=" * 70)

    finally:
        cleanup(envelope_id)

        print("\n[6] CLEANUP")
        print("test record removed")


if __name__ == "__main__":
    main()
