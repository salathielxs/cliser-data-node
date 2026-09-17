from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4
from runtime.protocol import create_request


@dataclass(frozen=True)
class AutomationRule:
    rule_id: str
    name: str
    event_type: str
    action: str
    enabled: bool = True
    condition: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AutomationExecution:
    execution_id: str
    rule_id: str
    event_id: str
    action: str
    timestamp: str
    status: str
    result: Any = None
    error: str | None = None


class AutomationEngine:
    """
    Automation Engine local da CLISER Cell.

    Responsabilidades:
    - registrar regras;
    - identificar eventos compatíveis;
    - avaliar condições;
    - executar ações registradas;
    - registrar o resultado da execução.

    Não possui persistência própria e não executa ações
    fora das funções explicitamente registradas.
    """

    def __init__(self) -> None:
        self._rules: dict[str, AutomationRule] = {}
        self._actions: dict[str, Callable[..., Any]] = {}
        self._executions: list[AutomationExecution] = []

    def register_action(
        self,
        name: str,
        action: Callable[..., Any],
    ) -> None:
        if not name:
            raise ValueError("action name inválido.")

        if not callable(action):
            raise TypeError("action deve ser callable.")

        self._actions[name] = action

    def register_service_action(
        self,
        name: str,
        service: str,
        operation: str,
        runtime: Any,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        if not name:
            raise ValueError("action name inválido.")

        if not service:
            raise ValueError("service inválido.")

        if not operation:
            raise ValueError("operation inválida.")

        if runtime is None:
            raise ValueError("runtime inválido.")

        arguments = dict(kwargs or {})

        def service_action(event: Any) -> Any:
            request = create_request(
                service,
                operation,
                parameters=arguments,
                metadata={
                    "source": "automation",
                    "event_id": getattr(event, "event_id", None),
                },
            )

            response = runtime.execute_request(request)

            if not response.success:
                raise RuntimeError(
                    response.error or "Protocol request failed."
                )

            return response.result

        self.register_action(
            name,
            service_action,
        )

    def register_rule(
        self,
        name: str,
        event_type: str,
        action: str,
        condition: dict[str, Any] | None = None,
    ) -> AutomationRule:

        if not name:
            raise ValueError("rule name inválido.")

        if not event_type:
            raise ValueError("event_type inválido.")

        if action not in self._actions:
            raise KeyError(
                f"Action not registered: {action}"
            )

        rule = AutomationRule(
            rule_id=uuid4().hex,
            name=name,
            event_type=event_type,
            action=action,
            condition=dict(condition or {}),
        )

        self._rules[rule.rule_id] = rule

        return rule

    def rules(self) -> list[AutomationRule]:
        return list(self._rules.values())

    def executions(self) -> list[AutomationExecution]:
        return list(self._executions)

    def _matches_condition(
        self,
        event: Any,
        condition: dict[str, Any],
    ) -> bool:

        if not condition:
            return True

        data = getattr(event, "data", {})

        for key, expected in condition.items():
            if data.get(key) != expected:
                return False

        return True

    def process_event(self, event: Any) -> list[AutomationExecution]:
        executions: list[AutomationExecution] = []

        for rule in self._rules.values():

            if not rule.enabled:
                continue

            if rule.event_type != event.event_type:
                continue

            if not self._matches_condition(
                event,
                rule.condition,
            ):
                continue

            execution_id = uuid4().hex

            try:
                action = self._actions[rule.action]

                result = action(event=event)

                execution = AutomationExecution(
                    execution_id=execution_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    action=rule.action,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status="SUCCESS",
                    result=result,
                )

            except Exception as exc:
                execution = AutomationExecution(
                    execution_id=execution_id,
                    rule_id=rule.rule_id,
                    event_id=event.event_id,
                    action=rule.action,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    status="ERROR",
                    error=str(exc),
                )

            self._executions.append(execution)
            executions.append(execution)

        return executions

    def state(self) -> dict[str, Any]:
        return {
            "rules": len(self._rules),
            "actions": len(self._actions),
            "executions": len(self._executions),
        }
