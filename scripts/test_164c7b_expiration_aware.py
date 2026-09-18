from datetime import datetime, timezone, timedelta

from node.registry import connect, reserve_replay


PREFIX = "TEST-16.4-C.7-B"


def cleanup():
    conn = connect()
    try:
        conn.execute(
            """
            DELETE FROM replay_records
            WHERE envelope_id LIKE ?
            """,
            (PREFIX + "%",),
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


def count_record(envelope_id):
    conn = connect()
    try:
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM replay_records
            WHERE envelope_id = ?
            """,
            (envelope_id,),
        ).fetchone()[0]
    finally:
        conn.close()


def main():
    cleanup()

    now = datetime.now(timezone.utc)

    new_id = PREFIX + "-NEW"
    valid_id = PREFIX + "-VALID"
    expired_id = PREFIX + "-EXPIRED"

    print("=" * 70)
    print("16.4-C.7-B — EXPIRATION-AWARE FUNCTIONAL TEST")
    print("=" * 70)

    # ----------------------------------------------------------
    # 1. NOVO ENVELOPE
    # ----------------------------------------------------------

    print()
    print("[1] NEW ENVELOPE")

    result = reserve_replay(
        envelope_id=new_id,
        source_peer_id="peer-new",
        source_node_id="node-new",
        received_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=60)).isoformat(),
    )

    print("reserve:", result)

    assert result is True
    assert count_record(new_id) == 1

    print("RESULT: PASS")

    # ----------------------------------------------------------
    # 2. REPLAY DE REGISTRO VÁLIDO
    # ----------------------------------------------------------

    print()
    print("[2] VALID RECORD — REPLAY")

    result = reserve_replay(
        envelope_id=new_id,
        source_peer_id="peer-new",
        source_node_id="node-new",
        received_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=60)).isoformat(),
    )

    print("reserve:", result)

    assert result is False
    assert count_record(new_id) == 1

    print("RESULT: REPLAY BLOCKED")

    # ----------------------------------------------------------
    # 3. CRIA REGISTRO EXPLICITAMENTE VÁLIDO
    # ----------------------------------------------------------

    print()
    print("[3] VALID RECORD")

    result = reserve_replay(
        envelope_id=valid_id,
        source_peer_id="peer-valid",
        source_node_id="node-valid",
        received_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=60)).isoformat(),
    )

    print("reserve:", result)

    assert result is True

    # ----------------------------------------------------------
    # 4. CRIA REGISTRO EXPIRADO
    # ----------------------------------------------------------

    print()
    print("[4] EXPIRED RECORD")

    old_received = now - timedelta(seconds=120)
    old_expires = now - timedelta(seconds=60)

    result = reserve_replay(
        envelope_id=expired_id,
        source_peer_id="peer-old",
        source_node_id="node-old",
        received_at=old_received.isoformat(),
        expires_at=old_expires.isoformat(),
    )

    print("initial reserve:", result)

    assert result is True

    record = get_record(expired_id)

    print("before renewal:", record)

    assert record is not None
    assert record[1] == "peer-old"
    assert record[2] == "node-old"

    print("RESULT: EXPIRED RECORD CREATED")

    # ----------------------------------------------------------
    # 5. RENOVAÇÃO ATÔMICA
    # ----------------------------------------------------------

    print()
    print("[5] EXPIRATION-AWARE RENEWAL")

    renewal_received = now
    renewal_expires = now + timedelta(seconds=60)

    result = reserve_replay(
        envelope_id=expired_id,
        source_peer_id="peer-renewed",
        source_node_id="node-renewed",
        received_at=renewal_received.isoformat(),
        expires_at=renewal_expires.isoformat(),
    )

    print("renewal:", result)

    assert result is True

    record = get_record(expired_id)

    print("after renewal:", record)

    assert record is not None
    assert record[1] == "peer-renewed"
    assert record[2] == "node-renewed"
    assert record[3] == renewal_received.isoformat()
    assert record[4] == renewal_expires.isoformat()

    assert count_record(expired_id) == 1

    print("RESULT: ATOMIC RENEWAL PASS")

    # ----------------------------------------------------------
    # 6. REPLAY APÓS RENOVAÇÃO
    # ----------------------------------------------------------

    print()
    print("[6] RENEWED RECORD — REPLAY")

    result = reserve_replay(
        envelope_id=expired_id,
        source_peer_id="peer-renewed",
        source_node_id="node-renewed",
        received_at=renewal_received.isoformat(),
        expires_at=renewal_expires.isoformat(),
    )

    print("replay:", result)

    assert result is False
    assert count_record(expired_id) == 1

    print("RESULT: REPLAY BLOCKED")

    # ----------------------------------------------------------
    # 7. PERSISTÊNCIA
    # ----------------------------------------------------------

    print()
    print("[7] PERSISTENCE")

    record = get_record(expired_id)

    print("persisted:", record)

    assert record is not None
    assert record[1] == "peer-renewed"
    assert record[2] == "node-renewed"

    print("RESULT: PERSISTENCE PASS")

    # ----------------------------------------------------------
    # 8. CLEANUP
    # ----------------------------------------------------------

    print()
    print("[8] CLEANUP")

    cleanup()

    assert count_record(new_id) == 0
    assert count_record(valid_id) == 0
    assert count_record(expired_id) == 0

    print("cleanup: PASS")

    print()
    print("=" * 70)
    print("16.4-C.7-B — ISOLATED FUNCTIONAL TEST: PASS")
    print("=" * 70)


if __name__ == "__main__":
    main()
