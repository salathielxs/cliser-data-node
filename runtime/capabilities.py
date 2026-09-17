from __future__ import annotations

from typing import Any


class CapabilityRegistry:
    """
    Registro das capacidades lógicas disponíveis na Cell.

    Capabilities descrevem o que o Runtime consegue executar.
    Authorization/permissions continuam sendo responsabilidade
    de node.access_control.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Any]] = {
            "data": {
                "status": "AVAILABLE",
                "description": "Persistent object data management",
                "operations": [
                    "create_object",
                    "get_object",
                    "read_object_data",
                    "verify_object",
                    "delete_object",
                    "list_namespace_objects",
                ],
                "permissions": [
                    "object.create",
                    "object.read",
                    "object.delete",
                ],
            },
            "namespace": {
                "status": "AVAILABLE",
                "description": "Namespace lifecycle management",
                "operations": [
                    "create_namespace",
                    "list_namespaces",
                    "get_namespace",
                    "enable_namespace",
                    "disable_namespace",
                ],
                "permissions": [
                    "namespace.read",
                    "namespace.manage",
                ],
            },
            "metrics": {
                "status": "AVAILABLE",
                "description": "Node and storage metrics",
                "operations": [
                    "get_metrics",
                ],
                "permissions": [
                    "node.manage",
                ],
            },
            "lifecycle": {
                "status": "AVAILABLE",
                "description": "Storage lifecycle and integrity operations",
                "operations": [
                    "garbage_collect",
                    "integrity_check",
                    "rebuild_refcounts",
                ],
                "permissions": [
                    "node.manage",
                ],
            },
        }

    def state(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "status": capability["status"],
                "description": capability["description"],
                "operations": sorted(capability["operations"]),
                "permissions": sorted(capability["permissions"]),
            }
            for name, capability in self._capabilities.items()
        }

    def get(self, name: str) -> dict[str, Any]:
        capability = self._capabilities.get(name)

        if capability is None:
            raise KeyError(f"Capability not found: {name}")

        return capability

    def has(self, name: str) -> bool:
        return name in self._capabilities
