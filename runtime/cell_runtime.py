from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from node.identity import load_identity
from node.health import run_health
from node.metrics import storage_metrics
from node.lifecycle import lifecycle_status
from runtime.capabilities import CapabilityRegistry
from runtime.events import EventLayer, RuntimeEvent
from runtime.automation import AutomationEngine
from runtime.protocol import CellRequest, CellResponse

from api.services.object_service import (
    create_object,
    get_object,
    verify_object_service,
    delete_object,
    list_namespace_objects,
    read_object_data,
)

from api.services.namespace_service import (
    create_namespace,
    list_namespaces,
    get_namespace,
    enable_namespace,
    disable_namespace,
)

from api.services.metrics_service import get_metrics

from api.services.lifecycle_service import (
    garbage_collect,
    rebuild_refcounts,
    integrity_check,
)


class CellRuntime:
    """
    Runtime operacional mínimo da CLISER Cell.

    O Runtime não implementa storage, registry, health ou lifecycle.
    Ele compõe e expõe os serviços existentes do Data Node.
    """

    RUNTIME_STATES = {
        "CREATED",
        "STARTING",
        "READY",
        "DEGRADED",
        "STOPPING",
        "STOPPED",
    }

    def __init__(self) -> None:
        self.identity = load_identity()
        self.capabilities = CapabilityRegistry()
        self.event_layer = EventLayer(
            self.identity["node_id"]
        )
        self.automation = AutomationEngine()
        self._runtime_state = "CREATED"

        self.services: dict[str, dict[str, Any]] = {
            "data": {
                "status": "AVAILABLE",
                "operations": {
                    "create_object": create_object,
                    "get_object": get_object,
                    "read_object_data": read_object_data,
                    "verify_object": verify_object_service,
                    "delete_object": delete_object,
                    "list_namespace_objects": list_namespace_objects,
                },
            },
            "namespace": {
                "status": "AVAILABLE",
                "operations": {
                    "create_namespace": create_namespace,
                    "list_namespaces": list_namespaces,
                    "get_namespace": get_namespace,
                    "enable_namespace": enable_namespace,
                    "disable_namespace": disable_namespace,
                },
            },
            "metrics": {
                "status": "AVAILABLE",
                "operations": {
                    "get_metrics": get_metrics,
                },
            },
            "lifecycle": {
                "status": "AVAILABLE",
                "operations": {
                    "garbage_collect": garbage_collect,
                    "rebuild_refcounts": rebuild_refcounts,
                    "integrity_check": integrity_check,
                },
            },
        }

    @property
    def runtime_state(self) -> str:
        return self._runtime_state

    def set_runtime_state(self, state: str) -> str:
        if state not in self.RUNTIME_STATES:
            raise ValueError(f"Invalid runtime state: {state}")

        previous_state = self._runtime_state

        self._runtime_state = state

        if previous_state != state:
            self.emit_event(
                "RUNTIME_STATE_CHANGED",
                {
                    "previous_state": previous_state,
                    "state": state,
                },
            )

        return self._runtime_state

    def runtime_state_info(self) -> dict[str, Any]:
        return {
            "state": self._runtime_state,
            "allowed_states": sorted(self.RUNTIME_STATES),
        }

    def emit_event(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        event = self.event_layer.emit(
            event_type,
            data=data,
        )

        self.automation.process_event(event)

        return event

    def event_state(self) -> dict[str, Any]:
        latest = self.event_layer.latest()

        return {
            "count": self.event_layer.count(),
            "latest": (
                {
                    "event_id": latest.event_id,
                    "event_type": latest.event_type,
                    "timestamp": latest.timestamp,
                    "node_id": latest.node_id,
                    "data": dict(latest.data),
                }
                if latest is not None
                else None
            ),
        }

    def event_history(self) -> list[RuntimeEvent]:
        return self.event_layer.history()

    def identity_state(self) -> dict[str, Any]:
        return dict(self.identity)

    def health_state(self) -> dict[str, Any]:
        return run_health()

    def metrics_state(self) -> dict[str, Any]:
        return storage_metrics()

    def lifecycle_state(self) -> dict[str, Any]:
        return lifecycle_status()

    def capability_state(self) -> dict[str, dict[str, Any]]:
        return self.capabilities.state()

    def service_state(self) -> dict[str, Any]:
        return {
            name: {
                "status": service["status"],
                "operations": sorted(service["operations"].keys()),
            }
            for name, service in self.services.items()
        }

    def get_service(self, name: str) -> dict[str, Any]:
        service = self.services.get(name)

        if service is None:
            raise KeyError(f"Service not found: {name}")

        return service

    def get_operation(self, service: str, operation: str) -> Callable[..., Any]:
        service_state = self.get_service(service)

        if service_state["status"] != "AVAILABLE":
            raise RuntimeError(f"Service unavailable: {service}")

        operation_fn = service_state["operations"].get(operation)

        if operation_fn is None:
            raise KeyError(
                f"Operation not found: {service}.{operation}"
            )

        return operation_fn

    def operate(
        self,
        service: str,
        operation: str,
        **kwargs: Any,
    ) -> Any:
        operation_fn = self.get_operation(
            service,
            operation,
        )

        return operation_fn(**kwargs)

    def execute_request(
        self,
        request: CellRequest,
    ) -> CellResponse:
        if not isinstance(request, CellRequest):
            raise TypeError("request deve ser CellRequest.")

        try:
            request.validate()

            parameters = dict(request.parameters)

            if request.namespace is not None:
                if "namespace" in parameters:
                    if parameters["namespace"] != request.namespace:
                        raise ValueError(
                            "namespace conflitante entre request "
                            "e parameters."
                        )
                else:
                    parameters["namespace"] = request.namespace

            result = self.operate(
                request.service,
                request.operation,
                **parameters,
            )

            return CellResponse(
                request_id=request.request_id,
                status="SUCCESS",
                service=request.service,
                operation=request.operation,
                result=result,
                metadata=dict(request.metadata),
            )

        except Exception as exc:
            return CellResponse(
                request_id=request.request_id,
                status="ERROR",
                service=request.service,
                operation=request.operation,
                error=str(exc),
                metadata=dict(request.metadata),
            )

    def operational_manifest(self) -> dict[str, Any]:
        """
        Representação operacional consolidada da Cell.

        O manifesto descreve identidade, runtime, capacidades,
        serviços, saúde, métricas e lifecycle.
        """
        health = self.health_state()

        return {
            "manifest": {
                "type": "cliser.cell.operational_manifest",
                "version": "1",
                "status": "ACTIVE",
            },
            "cell": {
                "identity": self.identity_state(),
            },
            "runtime": {
                "status": self._runtime_state,
            },
            "capabilities": self.capability_state(),
            "services": self.service_state(),
            "health": health,
            "metrics": self.metrics_state(),
            "lifecycle": self.lifecycle_state(),
        }

    def snapshot(self) -> dict[str, Any]:
        health = self.health_state()

        return {
            "runtime": {
                "status": self._runtime_state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "identity": self.identity_state(),
            "health": health,
            "metrics": self.metrics_state(),
            "lifecycle": self.lifecycle_state(),
            "capabilities": self.capability_state(),
            "services": self.service_state(),
            "events": self.event_state(),
        }

    def boot(self) -> dict[str, Any]:
        self.emit_event(
            "CELL_STARTING",
            {
                "runtime_state": self.runtime_state,
            },
        )

        self.set_runtime_state("STARTING")

        snapshot = self.snapshot()
        health_status = snapshot["health"].get("status")

        if health_status == "HEALTHY":
            self.set_runtime_state("READY")

            self.emit_event(
                "CELL_READY",
                {
                    "runtime_state": self.runtime_state,
                    "health": health_status,
                },
            )
        else:
            self.set_runtime_state("DEGRADED")

            self.emit_event(
                "CELL_DEGRADED",
                {
                    "runtime_state": self.runtime_state,
                    "health": health_status,
                },
            )

        return self.snapshot()

    def shutdown(self) -> dict[str, Any]:
        self.emit_event(
            "CELL_STOPPING",
            {
                "runtime_state": self.runtime_state,
            },
        )

        self.set_runtime_state("STOPPING")
        self.set_runtime_state("STOPPED")

        self.emit_event(
            "CELL_STOPPED",
            {
                "runtime_state": self.runtime_state,
            },
        )

        return self.snapshot()

    def recover(self) -> dict[str, Any]:
        self.emit_event(
            "CELL_RECOVERY_STARTED",
            {
                "runtime_state": self.runtime_state,
            },
        )

        self.set_runtime_state("STARTING")

        snapshot = self.snapshot()
        health_status = snapshot["health"].get("status")

        if health_status == "HEALTHY":
            self.set_runtime_state("READY")

            self.emit_event(
                "CELL_RECOVERED",
                {
                    "runtime_state": self.runtime_state,
                    "health": health_status,
                },
            )
        else:
            self.set_runtime_state("DEGRADED")

            self.emit_event(
                "CELL_DEGRADED",
                {
                    "runtime_state": self.runtime_state,
                    "health": health_status,
                },
            )

        return self.snapshot()


def create_runtime() -> CellRuntime:
    return CellRuntime()
