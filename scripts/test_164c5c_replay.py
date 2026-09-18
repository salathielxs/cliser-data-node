from getpass import getpass

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


def main():
    print("=" * 70)
    print("16.4-C.5-C — AUTOMATED FUNCTIONAL REPLAY TEST")
    print("=" * 70)

    identity = crypto_identity.load_identity()
    fingerprint = identity["fingerprint"]

    authorization = get_peer_authorization_by_fingerprint(fingerprint)

    if authorization is None:
        raise RuntimeError("Nenhuma autorização encontrada.")

    print("\n[1] AUTHORIZATION")
    print("identity_id:", authorization["identity_id"])
    print("role:", authorization["role"])
    print("namespace:", authorization["namespace"])
    print("status:", authorization["status"])

    if authorization["identity_id"] != TEST_IDENTITY:
        raise RuntimeError(
            f"identity_id inesperado: {authorization['identity_id']}"
        )

    if authorization["status"] != "REVOKED":
        raise RuntimeError(
            f"Estado inicial inesperado: {authorization['status']}"
        )

    envelope = None

    reactivate_peer_authorization(
        identity_id=authorization["identity_id"],
        fingerprint=authorization["fingerprint"],
        role=authorization["role"],
        namespace=authorization["namespace"],
    )

    print("\n[2] TEMPORARY AUTHORIZATION")
    print("status:", get_peer_authorization_by_fingerprint(
        fingerprint
    )["status"])

    try:
        print("\n[3] CRYPTOGRAPHIC IDENTITY")

        password = getpass("Senha da identidade: ")
        crypto_identity.unlock(password)

        print("algorithm:", identity["algorithm"])
        print("fingerprint:", fingerprint)
        print("unlocked:", crypto_identity.is_unlocked())

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
                "object_id": "TEST-16.4-C.5-C"
            },
        )

        envelope = create_envelope(
            source=source,
            target=target,
            request=request,
        ).sign()

        print("\n[4] ENVELOPE")
        print("envelope_id:", envelope.envelope_id)
        print("signature_valid:", envelope.verify_signature())

        envelope.validate_freshness()
        print("freshness: VALID")

        class FakeCapabilities:
            def permission_for(self, service, operation):
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
                        "object_id": request.parameters["object_id"],
                        "transport_test": True,
                    },
                )

        runtime = FakeRuntime()
        transport = LocalTransport()

        transport.register_target(
            TARGET_NODE,
            runtime,
        )

        print("\n[5] FIRST SEND")

        response = transport.send(envelope)

        print("status:", response.status)
        print("success:", response.success)
        print("runtime.calls:", runtime.calls)

        if not response.success:
            raise RuntimeError("Primeiro envio não retornou SUCCESS.")

        if runtime.calls != 1:
            raise RuntimeError(
                f"Esperado 1 chamada; obtido {runtime.calls}."
            )

        print("FIRST SEND: PASS")

        print("\n[6] REPLAY — SAME ENVELOPE")

        try:
            transport.send(envelope)

        except TransportReplayDetected as exc:
            print("EXPECTED:", exc)
            replay_detected = True

        else:
            replay_detected = False

        print("runtime.calls:", runtime.calls)

        if not replay_detected:
            raise RuntimeError("Replay não foi detectado.")

        if runtime.calls != 1:
            raise RuntimeError(
                "Replay alcançou execute_request()."
            )

        print("REPLAY DETECTION: PASS")
        print("RUNTIME BYPASS: PASS")

        print("\n[7] PERSISTENCE")

        conn = connect()

        try:
            row = conn.execute(
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
                (envelope.envelope_id,),
            ).fetchone()
        finally:
            conn.close()

        print("record:", row)

        if row is None:
            raise RuntimeError(
                "Replay record não foi persistido."
            )

        print("REPLAY PERSISTENCE: PASS")

        print("\n" + "=" * 70)
        print("16.4-C.5-C — AUTOMATED FUNCTIONAL TEST: PASS")
        print("=" * 70)

    finally:
        print("\n[8] CLEANUP")

        if envelope is not None:
            conn = connect()

            try:
                conn.execute(
                    """
                    DELETE FROM replay_records
                    WHERE envelope_id = ?
                    """,
                    (envelope.envelope_id,),
                )
                conn.commit()
            finally:
                conn.close()

        revoke_peer_authorization(TEST_IDENTITY)

        if crypto_identity.is_unlocked():
            crypto_identity.lock()

        final_auth = get_peer_authorization_by_fingerprint(
            fingerprint
        )

        print("authorization final:", final_auth["status"])
        print(
            "crypto identity locked:",
            not crypto_identity.is_unlocked(),
        )

        print("=" * 70)
        print("16.4-C.5-C — CLEANUP COMPLETE")
        print("=" * 70)


if __name__ == "__main__":
    main()
