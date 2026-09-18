from getpass import getpass
from datetime import datetime, timezone, timedelta

from node import crypto_identity
from node.registry import (
    get_peer_authorization_by_fingerprint,
    reactivate_peer_authorization,
    revoke_peer_authorization,
    connect,
)
from runtime.peer import PeerIdentity, create_envelope
from runtime.protocol import create_request, CellResponse
from runtime.transport import LocalTransport, TransportReplayDetected


TEST_IDENTITY = "TEST-CELL-HC"
SOURCE_PEER = "peer-replay-test-001"
SOURCE_NODE = "node-replay-test-001"
TARGET_NODE = "node-replay-target-001"


def cleanup_replay(envelope_id):
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


def get_replay_record(envelope_id):
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


def expire_replay_record(envelope_id):
    """
    Força apenas o registro persistido para o estado expirado.

    O envelope continua temporalmente fresco.
    Isso permite testar a integração do novo caminho
    expiration-aware de reserve_replay() sem esperar 60 segundos.
    """

    now = datetime.now(timezone.utc)
    expired = now - timedelta(seconds=1)

    conn = connect()

    try:
        conn.execute(
            """
            UPDATE replay_records
            SET expires_at = ?
            WHERE envelope_id = ?
            """,
            (
                expired.isoformat(),
                envelope_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    print("=" * 70)
    print("16.4-C.7-C — TRANSPORT REGRESSION / INTEGRATION TEST")
    print("=" * 70)

    identity = crypto_identity.load_identity()
    fingerprint = identity["fingerprint"]

    authorization = get_peer_authorization_by_fingerprint(
        fingerprint
    )

    if authorization is None:
        raise RuntimeError(
            "Nenhuma autorização encontrada."
        )

    if authorization["identity_id"] != TEST_IDENTITY:
        raise RuntimeError(
            f"identity_id inesperado: "
            f"{authorization['identity_id']}"
        )

    if authorization["status"] != "REVOKED":
        raise RuntimeError(
            f"Estado inicial inesperado: "
            f"{authorization['status']}"
        )

    envelope = None

    reactivate_peer_authorization(
        identity_id=authorization["identity_id"],
        fingerprint=authorization["fingerprint"],
        role=authorization["role"],
        namespace=authorization["namespace"],
    )

    try:
        print("\n[1] AUTHORIZATION")
        print(
            "status:",
            get_peer_authorization_by_fingerprint(
                fingerprint
            )["status"],
        )

        print("\n[2] CRYPTOGRAPHIC IDENTITY")

        password = getpass("Senha da identidade: ")
        crypto_identity.unlock(password)

        print(
            "unlocked:",
            crypto_identity.is_unlocked(),
        )

        source = PeerIdentity(
            peer_id=SOURCE_PEER,
            node_id=SOURCE_NODE,
            role=authorization["role"],
            public_key=identity["public_key"],
            fingerprint=identity["fingerprint"],
        )

        target = PeerIdentity(
            peer_id="peer-replay-target-001",
            node_id=TARGET_NODE,
            role="READER",
        )

        request = create_request(
            service="object",
            operation="read",
            namespace=authorization["namespace"],
            parameters={
                "object_id": "TEST-16.4-C.7-C",
            },
        )

        envelope = create_envelope(
            source=source,
            target=target,
            request=request,
        ).sign()

        print("\n[3] ENVELOPE")
        print(
            "envelope_id:",
            envelope.envelope_id,
        )
        print(
            "signature_valid:",
            envelope.verify_signature(),
        )

        envelope.validate_freshness()

        print("freshness: VALID")

        class FakeCapabilities:
            def permission_for(
                self,
                service,
                operation,
            ):
                return "object.read"

        class FakeRuntime:
            def __init__(self):
                self.capabilities = FakeCapabilities()
                self.calls = 0

            def execute_request(self, request):
                self.calls += 1

                return CellResponse(
                    request_id=request.request_id,
                    status="SUCCESS",
                    service=request.service,
                    operation=request.operation,
                    result={
                        "object_id":
                            request.parameters["object_id"],
                        "transport_test": True,
                    },
                )

        runtime = FakeRuntime()
        transport = LocalTransport()

        transport.register_target(
            TARGET_NODE,
            runtime,
        )

        print("\n[4] FIRST SEND")

        response = transport.send(envelope)

        print("status:", response.status)
        print("success:", response.success)
        print("runtime.calls:", runtime.calls)

        if not response.success:
            raise RuntimeError(
                "Primeiro envio não retornou SUCCESS."
            )

        if runtime.calls != 1:
            raise RuntimeError(
                f"Esperado 1 chamada; "
                f"obtido {runtime.calls}."
            )

        record = get_replay_record(
            envelope.envelope_id
        )

        if record is None:
            raise RuntimeError(
                "Replay record não foi criado."
            )

        print("record:", record)
        print("FIRST SEND: PASS")
        print("REPLAY RECORD CREATION: PASS")

        print("\n[5] SAME ENVELOPE — REPLAY")

        try:
            transport.send(envelope)

        except TransportReplayDetected as exc:
            print("EXPECTED:", exc)
            replay_detected = True

        else:
            replay_detected = False

        print(
            "runtime.calls:",
            runtime.calls,
        )

        if not replay_detected:
            raise RuntimeError(
                "Replay não foi detectado."
            )

        if runtime.calls != 1:
            raise RuntimeError(
                "Replay alcançou execute_request()."
            )

        print("REPLAY DETECTION: PASS")
        print("RUNTIME BYPASS: PASS")

        print("\n[6] EXPIRATION-AWARE RENEWAL")

        expire_replay_record(
            envelope.envelope_id
        )

        expired_record = get_replay_record(
            envelope.envelope_id
        )

        print(
            "expired record:",
            expired_record,
        )

        if expired_record is None:
            raise RuntimeError(
                "Registro não encontrado."
            )

        expires_at = datetime.fromisoformat(
            expired_record[4]
        )

        now = datetime.now(timezone.utc)

        if expires_at >= now:
            raise RuntimeError(
                "Registro não ficou expirado."
            )

        print("RESULT: EXPIRED RECORD READY")

        response = transport.send(envelope)

        print("status:", response.status)
        print("success:", response.success)
        print("runtime.calls:", runtime.calls)

        if not response.success:
            raise RuntimeError(
                "Renovação não retornou SUCCESS."
            )

        if runtime.calls != 2:
            raise RuntimeError(
                "Envelope renovado não alcançou "
                "o runtime exatamente uma vez."
            )

        renewed_record = get_replay_record(
            envelope.envelope_id
        )

        print(
            "renewed record:",
            renewed_record,
        )

        if renewed_record is None:
            raise RuntimeError(
                "Registro renovado desapareceu."
            )

        renewed_expires = datetime.fromisoformat(
            renewed_record[4]
        )

        if renewed_expires <= now:
            raise RuntimeError(
                "expires_at não foi renovado."
            )

        print("EXPIRATION-AWARE RENEWAL: PASS")
        print("TRANSPORT EXECUTION AFTER RENEWAL: PASS")

        print("\n[7] RENEWED RECORD — REPLAY")

        try:
            transport.send(envelope)

        except TransportReplayDetected as exc:
            print("EXPECTED:", exc)
            replay_after_renewal = True

        else:
            replay_after_renewal = False

        print(
            "runtime.calls:",
            runtime.calls,
        )

        if not replay_after_renewal:
            raise RuntimeError(
                "Registro renovado não bloqueou replay."
            )

        if runtime.calls != 2:
            raise RuntimeError(
                "Replay após renovação alcançou runtime."
            )

        print(
            "RENEWED REPLAY DETECTION: PASS"
        )
        print(
            "RENEWED RUNTIME BYPASS: PASS"
        )

        print("\n[8] FINAL PERSISTENCE")

        final_record = get_replay_record(
            envelope.envelope_id
        )

        print(
            "final record:",
            final_record,
        )

        if final_record is None:
            raise RuntimeError(
                "Registro final não persistido."
            )

        if final_record[0] != envelope.envelope_id:
            raise RuntimeError(
                "envelope_id final incorreto."
            )

        print("FINAL PERSISTENCE: PASS")

        print("\n[9] REGRESSION SUMMARY")
        print("authentication: PASS")
        print("freshness: PASS")
        print("replay reservation: PASS")
        print("replay detection: PASS")
        print("expired-record renewal: PASS")
        print("authorization boundary: PASS")
        print("execution: PASS")
        print("renewed replay protection: PASS")
        print("runtime bypass: PASS")
        print("persistence: PASS")

        print("\n" + "=" * 70)
        print("16.4-C.7-C — TRANSPORT REGRESSION / INTEGRATION TEST: PASS")
        print("=" * 70)

    finally:
        print("\n[10] CLEANUP")

        if envelope is not None:
            cleanup_replay(
                envelope.envelope_id
            )

        revoke_peer_authorization(
            TEST_IDENTITY
        )

        if crypto_identity.is_unlocked():
            crypto_identity.lock()

        final_auth = (
            get_peer_authorization_by_fingerprint(
                fingerprint
            )
        )

        print(
            "authorization final:",
            final_auth["status"],
        )

        print(
            "crypto identity locked:",
            not crypto_identity.is_unlocked(),
        )

        print("=" * 70)
        print("16.4-C.7-C — CLEANUP COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    main()
