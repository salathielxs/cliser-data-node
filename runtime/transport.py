from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Protocol

from runtime.peer import CellEnvelope
from node.registry import reserve_replay
from runtime.protocol import CellResponse
from node.access_control import require_permission
from node.namespace_security import require_namespace_access
from node.peer_authorization import resolve_principal_from_envelope


class TransportError(Exception):
    """Erro base da camada de transporte."""


class TransportTargetNotFound(TransportError):
    """Destino do transporte não encontrado."""


class TransportReplayDetected(TransportError):
    """Envelope já processado pelo transporte."""


class TransportProtocol(Protocol):
    """
    Contrato mínimo para transporte entre Cells.

    O transporte recebe um CellEnvelope e devolve
    uma CellResponse.
    """

    def send(self, envelope: CellEnvelope) -> CellResponse:
        ...


@dataclass(frozen=True)
class TransportResult:
    """
    Resultado operacional do transporte.

    Mantém o envelope associado à resposta recebida.
    """

    envelope_id: str
    response: CellResponse

    @property
    def success(self) -> bool:
        return self.response.success


class LocalTransport:
    """
    Transporte local/in-process entre Cells.

    Não utiliza rede, sockets ou HTTP.

    Serve como primeira implementação do contrato de transporte
    antes da introdução de um transporte físico/remoto.
    """

    def __init__(self) -> None:
        self._targets: dict[str, object] = {}

    def register_target(
        self,
        node_id: str,
        runtime: object,
    ) -> None:
        if not node_id:
            raise ValueError("node_id inválido.")

        if runtime is None:
            raise ValueError("runtime inválido.")

        if node_id in self._targets:
            raise ValueError(
                f"target já registrado: {node_id}"
            )

        if not hasattr(runtime, "execute_request"):
            raise TypeError(
                "runtime deve implementar execute_request()."
            )

        self._targets[node_id] = runtime

    def unregister_target(self, node_id: str) -> object:
        if not node_id:
            raise ValueError("node_id inválido.")

        try:
            return self._targets.pop(node_id)
        except KeyError:
            raise TransportTargetNotFound(
                f"target não encontrado: {node_id}"
            ) from None

    def get_target(self, node_id: str) -> object:
        if not node_id:
            raise ValueError("node_id inválido.")

        try:
            return self._targets[node_id]
        except KeyError:
            raise TransportTargetNotFound(
                f"target não encontrado: {node_id}"
            ) from None

    def send(self, envelope: CellEnvelope) -> CellResponse:
        if not isinstance(envelope, CellEnvelope):
            raise TypeError(
                "envelope deve ser CellEnvelope."
            )

        envelope.validate()

        # --------------------------------------------------------------
        # SECURITY GATE — AUTHENTICATION
        # --------------------------------------------------------------

        if not envelope.verify_signature():
            raise TransportError(
                "assinatura do CellEnvelope inválida."
            )

        # --------------------------------------------------------------
        # SECURITY GATE — FRESHNESS
        # --------------------------------------------------------------

        envelope.validate_freshness()

        # --------------------------------------------------------------
        # SECURITY GATE — REPLAY PROTECTION
        # --------------------------------------------------------------

        received_at = datetime.now(timezone.utc)
        envelope_timestamp = datetime.fromisoformat(
            envelope.timestamp
        )

        expires_at = (
            envelope_timestamp + timedelta(seconds=60)
        )

        reserved = reserve_replay(
            envelope_id=envelope.envelope_id,
            source_peer_id=envelope.source.peer_id,
            source_node_id=envelope.source_node_id,
            received_at=received_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

        if not reserved:
            raise TransportReplayDetected(
                f"replay detectado para envelope_id="
                f"{envelope.envelope_id}"
            )

        # --------------------------------------------------------------
        # SECURITY GATE — IDENTITY / AUTHORIZATION BOUNDARY
        # --------------------------------------------------------------

        principal = resolve_principal_from_envelope(
            envelope
        )

        target_runtime = self.get_target(
            envelope.target_node_id
        )

        permission = target_runtime.capabilities.permission_for(
            envelope.request.service,
            envelope.request.operation,
        )

        # Operações com namespace precisam respeitar simultaneamente:
        #   1. existência/estado do namespace
        #   2. escopo do Principal
        #   3. permissão RBAC
        if envelope.request.namespace is not None:
            require_namespace_access(
                principal,
                envelope.request.namespace,
                permission,
            )
        else:
            require_permission(
                principal,
                permission,
            )

        # --------------------------------------------------------------
        # SECURITY GATE — EXECUTION
        # --------------------------------------------------------------

        response = target_runtime.execute_request(
            envelope.request
        )

        # --------------------------------------------------------------
        # SECURITY GATE — RESPONSE BINDING
        # --------------------------------------------------------------

        if response.request_id != envelope.request.request_id:
            raise TransportError(
                "resposta incompatível: request_id não corresponde "
                "à request enviada."
            )

        if response.service != envelope.request.service:
            raise TransportError(
                "resposta incompatível: service não corresponde "
                "à request enviada."
            )

        if response.operation != envelope.request.operation:
            raise TransportError(
                "resposta incompatível: operation não corresponde "
                "à request enviada."
            )

        return response

    def send_result(
        self,
        envelope: CellEnvelope,
    ) -> TransportResult:
        response = self.send(envelope)

        return TransportResult(
            envelope_id=envelope.envelope_id,
            response=response,
        )

    def count(self) -> int:
        return len(self._targets)

    def clear(self) -> None:
        self._targets.clear()
