from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    event_type: str
    timestamp: str
    node_id: str
    data: dict[str, Any] = field(default_factory=dict)


class EventLayer:
    """
    Event Layer local da CLISER Cell.

    Responsabilidades:
    - criar eventos;
    - manter histórico em memória;
    - fornecer o último evento;
    - não persistir nem transmitir eventos.
    """

    def __init__(self, node_id: str) -> None:
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node_id inválido.")

        self.node_id = node_id
        self._events: list[RuntimeEvent] = []

    def emit(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> RuntimeEvent:

        if not isinstance(event_type, str) or not event_type:
            raise ValueError("event_type inválido.")

        event = RuntimeEvent(
            event_id=uuid4().hex,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=self.node_id,
            data=dict(data or {}),
        )

        self._events.append(event)

        return event

    def history(self) -> list[RuntimeEvent]:
        return list(self._events)

    def latest(self) -> RuntimeEvent | None:
        if not self._events:
            return None

        return self._events[-1]

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
