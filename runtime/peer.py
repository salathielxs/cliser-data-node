from __future__ import annotations

import base64

from dataclasses import dataclass, field
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.protocol import CellRequest, PROTOCOL_VERSION
from node import crypto_identity


@dataclass(frozen=True)
class PeerIdentity:
    """
    Identidade operacional de um Cell remoto.

    Representa a identidade operacional e criptográfica
    conhecida de um Cell remoto.
    A autenticidade é verificada pela assinatura Ed25519
    do CellEnvelope.
    """

    peer_id: str
    node_id: str
    role: str
    protocol_version: str = PROTOCOL_VERSION
    capabilities: tuple[str, ...] = ()
    status: str = "ACTIVE"
    public_key: str | None = None
    fingerprint: str | None = None

    def validate(self) -> None:
        if not self.peer_id:
            raise ValueError("peer_id inválido.")

        if not self.node_id:
            raise ValueError("node_id inválido.")

        if not self.role:
            raise ValueError("role inválido.")

        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(
                f"protocol_version não suportada: "
                f"{self.protocol_version}"
            )

        if not isinstance(self.capabilities, tuple):
            raise TypeError("capabilities deve ser uma tuple.")

        if self.status not in {"ACTIVE", "INACTIVE"}:
            raise ValueError("status de peer inválido.")

        if (self.public_key is None) != (self.fingerprint is None):
            raise ValueError(
                "public_key e fingerprint devem ser fornecidos juntos."
            )

        if self.public_key is not None:
            if not isinstance(self.public_key, str):
                raise TypeError(
                    "public_key deve ser uma string Base64."
                )

            if not isinstance(self.fingerprint, str):
                raise TypeError(
                    "fingerprint deve ser uma string."
                )

            try:
                public_key_bytes = base64.b64decode(
                    self.public_key.encode("ascii"),
                    validate=True,
                )
            except Exception as exc:
                raise ValueError(
                    "public_key não é Base64 válido."
                ) from exc

            if len(public_key_bytes) != 32:
                raise ValueError(
                    "public_key Ed25519 deve possuir 32 bytes."
                )

            expected_fingerprint = crypto_identity.fingerprint(
                Ed25519PublicKey.from_public_bytes(
                    public_key_bytes
                )
            )

            if self.fingerprint != expected_fingerprint:
                raise ValueError(
                    "fingerprint da public_key não confere."
                )


@dataclass(frozen=True)
class CellEnvelope:
    """
    Envelope de transporte entre Cells.

    O envelope identifica origem e destino, transporta
    uma CellRequest já validada e pode ser autenticado
    por assinatura Ed25519 da identidade de origem.
    """

    source: PeerIdentity
    target: PeerIdentity
    request: CellRequest
    envelope_id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    protocol_version: str = PROTOCOL_VERSION
    signature: str | None = None

    def sign(self) -> "CellEnvelope":
        """
        Assina o payload canônico do envelope usando a identidade local.

        A assinatura não faz parte do payload assinado, evitando
        dependência circular.
        """
        self.validate()

        payload = envelope_signing_payload(self)
        signature = crypto_identity.sign(payload)

        return CellEnvelope(
            source=self.source,
            target=self.target,
            request=self.request,
            envelope_id=self.envelope_id,
            timestamp=self.timestamp,
            protocol_version=self.protocol_version,
            signature=base64.b64encode(signature).decode("ascii"),
        )

    def verify_signature(self) -> bool:
        """
        Verifica a assinatura usando a chave pública declarada
        pela identidade de origem do envelope.
        """
        self.validate()

        if self.signature is None:
            return False

        if self.source.public_key is None:
            return False

        try:
            signature_bytes = base64.b64decode(
                self.signature.encode("ascii"),
                validate=True,
            )

            public_key_bytes = base64.b64decode(
                self.source.public_key.encode("ascii"),
                validate=True,
            )

            public_key = Ed25519PublicKey.from_public_bytes(
                public_key_bytes
            )

            payload = envelope_signing_payload(self)

            return crypto_identity.verify_with_public_key(
                payload,
                signature_bytes,
                public_key,
            )

        except Exception:
            return False

    def validate_freshness(
        self,
        now: datetime | None = None,
        max_age_seconds: float = 60.0,
        future_tolerance_seconds: float = 5.0,
    ) -> None:
        """
        Valida a validade temporal do envelope.

        A política é baseada no timestamp UTC autenticado pela assinatura:
        - idade máxima: 60 segundos;
        - tolerância para timestamp futuro: 5 segundos.

        ``now`` pode ser fornecido para validações determinísticas.
        """

        if not isinstance(max_age_seconds, (int, float)):
            raise TypeError(
                "max_age_seconds deve ser numérico."
            )

        if not isinstance(future_tolerance_seconds, (int, float)):
            raise TypeError(
                "future_tolerance_seconds deve ser numérico."
            )

        if max_age_seconds < 0:
            raise ValueError(
                "max_age_seconds não pode ser negativo."
            )

        if future_tolerance_seconds < 0:
            raise ValueError(
                "future_tolerance_seconds não pode ser negativo."
            )

        if now is None:
            now = datetime.now(timezone.utc)

        if not isinstance(now, datetime):
            raise TypeError(
                "now deve ser datetime."
            )

        if now.tzinfo is None:
            raise ValueError(
                "now deve possuir timezone."
            )

        now_utc = now.astimezone(timezone.utc)

        try:
            envelope_time = datetime.fromisoformat(
                self.timestamp
            )
        except Exception as exc:
            raise ValueError(
                "timestamp do envelope inválido."
            ) from exc

        if envelope_time.tzinfo is None:
            raise ValueError(
                "timestamp do envelope deve possuir timezone."
            )

        envelope_time_utc = envelope_time.astimezone(
            timezone.utc
        )

        age_seconds = (
            now_utc - envelope_time_utc
        ).total_seconds()

        if age_seconds > max_age_seconds:
            raise ValueError(
                "envelope expirado: timestamp fora da janela de freshness."
            )

        if age_seconds < -future_tolerance_seconds:
            raise ValueError(
                "envelope rejeitado: timestamp excessivamente futuro."
            )

    def validate(self) -> None:
        if not self.envelope_id:
            raise ValueError("envelope_id inválido.")

        if not isinstance(self.source, PeerIdentity):
            raise TypeError("source deve ser PeerIdentity.")

        if not isinstance(self.target, PeerIdentity):
            raise TypeError("target deve ser PeerIdentity.")

        if not isinstance(self.request, CellRequest):
            raise TypeError("request deve ser CellRequest.")

        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(
                f"protocol_version não suportada: "
                f"{self.protocol_version}"
            )

        self.source.validate()
        self.target.validate()
        self.request.validate()

    @property
    def source_node_id(self) -> str:
        return self.source.node_id

    @property
    def target_node_id(self) -> str:
        return self.target.node_id

    def metadata(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "source_peer_id": self.source.peer_id,
            "source_node_id": self.source.node_id,
            "target_peer_id": self.target.peer_id,
            "target_node_id": self.target.node_id,
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version,
        }


def create_peer_identity(
    *,
    peer_id: str,
    node_id: str,
    role: str,
    capabilities: list[str] | tuple[str, ...] | None = None,
    status: str = "ACTIVE",
    public_key: str | None = None,
    fingerprint: str | None = None,
) -> PeerIdentity:
    peer = PeerIdentity(
        peer_id=peer_id,
        node_id=node_id,
        role=role,
        capabilities=tuple(capabilities or ()),
        status=status,
        public_key=public_key,
        fingerprint=fingerprint,
    )

    peer.validate()

    return peer


def create_envelope(
    source: PeerIdentity,
    target: PeerIdentity,
    request: CellRequest,
) -> CellEnvelope:
    envelope = CellEnvelope(
        source=source,
        target=target,
        request=request,
    )

    envelope.validate()

    return envelope


class PeerRegistry:
    """
    Registro operacional de peers conhecidos pela Cell.

    O registro é mantido em memória nesta primeira versão.
    Persistência e descoberta remota serão adicionadas posteriormente.
    """

    def __init__(self) -> None:
        self._peers: dict[str, PeerIdentity] = {}

    def register(self, peer: PeerIdentity) -> PeerIdentity:
        if not isinstance(peer, PeerIdentity):
            raise TypeError("peer deve ser PeerIdentity.")

        peer.validate()

        if peer.peer_id in self._peers:
            raise ValueError(
                f"peer já registrado: {peer.peer_id}"
            )

        self._peers[peer.peer_id] = peer
        return peer

    def get(self, peer_id: str) -> PeerIdentity:
        if not peer_id:
            raise ValueError("peer_id inválido.")

        try:
            return self._peers[peer_id]
        except KeyError:
            raise KeyError(
                f"peer não encontrado: {peer_id}"
            ) from None

    def remove(self, peer_id: str) -> PeerIdentity:
        if not peer_id:
            raise ValueError("peer_id inválido.")

        try:
            return self._peers.pop(peer_id)
        except KeyError:
            raise KeyError(
                f"peer não encontrado: {peer_id}"
            ) from None

    def list_peers(self) -> list[PeerIdentity]:
        return list(self._peers.values())

    def count(self) -> int:
        return len(self._peers)

    def clear(self) -> None:
        self._peers.clear()


def peer_identity_from_runtime(runtime: Any) -> PeerIdentity:
    """
    Cria uma PeerIdentity a partir do estado operacional
    já existente no CellRuntime.

    Não cria nem altera a identidade da Cell.
    """

    if runtime is None:
        raise ValueError("runtime inválido.")

    identity = runtime.identity_state()
    capabilities_state = runtime.capability_state()

    node_id = identity.get("node_id")
    role = identity.get("role")

    if not node_id:
        raise ValueError("runtime sem node_id.")

    if not role:
        raise ValueError("runtime sem role.")

    peer_capabilities = tuple(
        sorted(capabilities_state.keys())
    )

    public_key = crypto_identity.load_public_key()
    public_key_bytes = public_key.public_bytes_raw()

    peer = PeerIdentity(
        peer_id=node_id,
        node_id=node_id,
        role=role,
        protocol_version=PROTOCOL_VERSION,
        capabilities=peer_capabilities,
        status="ACTIVE",
        public_key=base64.b64encode(
            public_key_bytes
        ).decode("ascii"),
        fingerprint=crypto_identity.fingerprint(
            public_key
        ),
    )

    peer.validate()

    return peer


def envelope_signing_payload(envelope: CellEnvelope) -> bytes:
    """
    Produz a representação canônica do envelope usada na assinatura.

    A serialização é determinística para que origem e destino
    possam produzir exatamente os mesmos bytes.
    """

    import json

    if not isinstance(envelope, CellEnvelope):
        raise TypeError(
            "envelope deve ser CellEnvelope."
        )

    envelope.validate()

    payload = {
        "envelope_id": envelope.envelope_id,
        "timestamp": envelope.timestamp,
        "protocol_version": envelope.protocol_version,
        "source_peer_id": envelope.source.peer_id,
        "source_node_id": envelope.source.node_id,
        "source_role": envelope.source.role,
        "target_peer_id": envelope.target.peer_id,
        "target_node_id": envelope.target.node_id,
        "target_role": envelope.target.role,
        "request_id": envelope.request.request_id,
        "request_service": envelope.request.service,
        "request_operation": envelope.request.operation,
        "request_namespace": envelope.request.namespace,
        "request_parameters": envelope.request.parameters,
        "request_protocol_version": envelope.request.protocol_version,
        "request_identity_id": envelope.request.identity_id,
        "request_metadata": envelope.request.metadata,
    }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
