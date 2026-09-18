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


def main():
    print("=" * 70)
    print("16.4-C.6-B — REPLAY EXPIRATION FORENSIC TEST")
    print("=" * 70)

    envelope_id = (
        "TEST-16.4-C.6-B-"
        + uuid4().hex
    )

    now = datetime.now(timezone.utc)

    expired_at = (
        now - timedelta(seconds=120)
    ).isoformat()

    received_at = (
        now - timedelta(seconds=180)
    ).isoformat()

    try:
        print("\n[1] INSERT EXPIRED RECORD")

        first = reserve_replay(
            envelope_id=envelope_id,
            source_peer_id="peer-expiration-test",
            source_node_id="node-expiration-test",
            received_at=received_at,
            expires_at=expired_at,
        )

        print("first reserve:", first)
        print("expires_at:", expired_at)

        if first is not True:
            raise RuntimeError(
                "Falha ao criar registro expirado."
            )

        print("RESULT: EXPIRED RECORD CREATED")

        print("\n[2] SECOND RESERVATION")

        second = reserve_replay(
            envelope_id=envelope_id,
            source_peer_id="peer-expiration-test",
            source_node_id="node-expiration-test",
            received_at=now.isoformat(),
            expires_at=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )

        print("second reserve:", second)

        if second is True:
            print(
                "RESULT: EXPIRED RECORD IS REUSABLE"
            )
        else:
            print(
                "RESULT: EXPIRED RECORD STILL BLOCKS REPLAY"
            )

        print("\n[3] DATABASE STATE")

        conn = connect()

        try:
            row = conn.execute(
                """
                SELECT
                    envelope_id,
                    received_at,
                    expires_at
                FROM replay_records
                WHERE envelope_id = ?
                """,
                (envelope_id,),
            ).fetchone()
        finally:
            conn.close()

        print("record:", row)

        print("\n" + "=" * 70)
        print("16.4-C.6-B — OBSERVATION COMPLETE")
        print("=" * 70)

    finally:
        cleanup(envelope_id)

        print("\n[4] CLEANUP")
        print("test record removed")


if __name__ == "__main__":
    main()
