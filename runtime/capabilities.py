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

    def permission_for(
        self,
        service: str,
        operation: str,
    ) -> str:
        """
        Resolve a permissão necessária para uma operação.

        A relação entre operação e permissão pertence à
        definição da Capability. A matriz de autorização
        continua sendo responsabilidade de node.access_control.
        """
        capability = self.get(service)

        operations = capability["operations"]
        permissions = capability["permissions"]

        if operation not in operations:
            raise KeyError(
                f"Operation not found: {service}.{operation}"
            )

        if service == "data":
            mapping = {
                "create_object": "object.create",
                "get_object": "object.read",
                "read_object_data": "object.read",
                "verify_object": "object.read",
                "delete_object": "object.delete",
                "list_namespace_objects": "object.read",
            }

        elif service == "namespace":
            mapping = {
                "create_namespace": "namespace.manage",
                "list_namespaces": "namespace.read",
                "get_namespace": "namespace.read",
                "enable_namespace": "namespace.manage",
                "disable_namespace": "namespace.manage",
            }

        elif service == "metrics":
            mapping = {
                "get_metrics": "node.manage",
            }

        elif service == "lifecycle":
            mapping = {
                "garbage_collect": "node.manage",
                "integrity_check": "node.manage",
                "rebuild_refcounts": "node.manage",
            }

        else:
            raise KeyError(
                f"No permission mapping for capability: {service}"
            )

        permission = mapping.get(operation)

        if permission is None:
            raise KeyError(
                f"No permission mapping for operation: "
                f"{service}.{operation}"
            )

        if permission not in permissions:
            raise ValueError(
                f"Permission {permission} is not declared "
                f"by capability {service}."
            )

        return permission

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
