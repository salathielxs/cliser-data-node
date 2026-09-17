from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


PROTOCOL_VERSION = "1"


@dataclass(frozen=True)
class CellRequest:
    """
    Solicitação operacional interna da CLISER Cell.

    O protocolo descreve a intenção.
    O Runtime continua responsável pela execução.
    """

    service: str
    operation: str
    namespace: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    protocol_version: str = PROTOCOL_VERSION
    identity_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.service:
            raise ValueError("service inválido.")

        if not self.operation:
            raise ValueError("operation inválida.")

        if not isinstance(self.parameters, dict):
            raise TypeError("parameters deve ser um dict.")

        if not isinstance(self.metadata, dict):
            raise TypeError("metadata deve ser um dict.")

        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(
                f"protocol_version não suportada: "
                f"{self.protocol_version}"
            )


@dataclass(frozen=True)
class CellResponse:
    """
    Resultado padronizado de uma operação da Cell.
    """

    request_id: str
    status: str
    service: str
    operation: str
    result: Any = None
    error: str | None = None
    protocol_version: str = PROTOCOL_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == "SUCCESS"


def create_request(
    service: str,
    operation: str,
    *,
    namespace: str | None = None,
    parameters: dict[str, Any] | None = None,
    identity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CellRequest:
    request = CellRequest(
        service=service,
        operation=operation,
        namespace=namespace,
        parameters=dict(parameters or {}),
        identity_id=identity_id,
        metadata=dict(metadata or {}),
    )

    request.validate()

    return request
