from datetime import datetime, timezone, timedelta
from uuid import uuid4

from node.registry import reserve_replay, connect


def cleanup(ids):
    conn = connect()
    try:
        for envelope_id in ids:
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


def get_record(envelope_id):
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
            (envelope_id,),
        ).fetchone()
    finally:
        conn.close()


def main():
    print("=" * 70)
    print("16.4-C.6-C — REPLAY LIFECYCLE POLICY FORENSIC")
    print("=" * 70)

    now = datetime.now(timezone.utc)

    valid_id = "TEST-16.4-C.6-C-VALID-" + uuid4().hex
    expired_id = "TEST-16.4-C.6-C-EXPIRED-" + uuid4().hex
    new_id = "TEST-16.4-C.6-C-NEW-" + uuid4().hex

    test_ids = [valid_id, expired_id, new_id]

    try:
        # ==============================================================
        # 1. VALID RECORD
        # ==============================================================

        print("\n[1] VALID REPLAY RECORD")

        valid = reserve_replay(
            envelope_id=valid_id,
            source_peer_id="peer-lifecycle-test",
            source_node_id="node-lifecycle-test",
            received_at=now.isoformat(),
            expires_at=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )

        print("first reserve:", valid)

        valid_replay = reserve_replay(
            envelope_id=valid_id,
            source_peer_id="peer-lifecycle-test",
            source_node_id="node-lifecycle-test",
            received_at=now.isoformat(),
            expires_at=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )

        print("second reserve:", valid_replay)

        if valid is True and valid_replay is False:
            print("RESULT: VALID RECORD BLOCKS REPLAY")
        else:
            print("RESULT: UNEXPECTED VALID-RECORD BEHAVIOR")

        # ==============================================================
        # 2. EXPIRED RECORD
        # ==============================================================

        print("\n[2] EXPIRED REPLAY RECORD")

        expired = reserve_replay(
            envelope_id=expired_id,
            source_peer_id="peer-lifecycle-test",
            source_node_id="node-lifecycle-test",
            received_at=(
                now - timedelta(seconds=180)
            ).isoformat(),
            expires_at=(
                now - timedelta(seconds=120)
            ).isoformat(),
        )

        print("first reserve:", expired)

        expired_replay = reserve_replay(
            envelope_id=expired_id,
            source_peer_id="peer-lifecycle-test",
            source_node_id="node-lifecycle-test",
            received_at=now.isoformat(),
            expires_at=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )

        print("second reserve:", expired_replay)

        if expired_replay is False:
            print(
                "RESULT: EXPIRED RECORD STILL BLOCKS REPLAY"
            )
        else:
            print(
                "RESULT: EXPIRED RECORD IS REUSABLE"
            )

        # ==============================================================
        # 3. NEW ENVELOPE
        # ==============================================================

        print("\n[3] NEW ENVELOPE")

        new_result = reserve_replay(
            envelope_id=new_id,
            source_peer_id="peer-lifecycle-test",
            source_node_id="node-lifecycle-test",
            received_at=now.isoformat(),
            expires_at=(
                now + timedelta(seconds=60)
            ).isoformat(),
        )

        print("new reserve:", new_result)

        if new_result is True:
            print("RESULT: NEW ENVELOPE ACCEPTED")
        else:
            print("RESULT: UNEXPECTED NEW-ENVELOPE FAILURE")

        # ==============================================================
        # 4. DATABASE SNAPSHOT
        # ==============================================================

        print("\n[4] DATABASE SNAPSHOT")

        for envelope_id in test_ids:
            print(get_record(envelope_id))

        # ==============================================================
        # 5. POLICY OBSERVATION
        # ==============================================================

        print("\n[5] POLICY OBSERVATION")

        print("valid record:")
        print("  replay blocked =", valid_replay is False)

        print("expired record:")
        print("  replay blocked =", expired_replay is False)

        print("new envelope:")
        print("  accepted =", new_result is True)

        print("\n" + "=" * 70)
        print("16.4-C.6-C — FORENSIC OBSERVATION COMPLETE")
        print("=" * 70)

    finally:
        cleanup(test_ids)

        print("\n[6] CLEANUP")
        print("test records removed")


if __name__ == "__main__":
    main()
