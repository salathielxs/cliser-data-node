from __future__ import annotations

from node import namespace_manager


def create_namespace(
    namespace: str,
    quota_bytes: int = 0,
):
    return namespace_manager.create_namespace(
        namespace=namespace,
        quota_bytes=quota_bytes,
    )


def list_namespaces(status: str | None = None):
    return namespace_manager.list_namespaces(
        status=status,
    )


def get_namespace(namespace: str):
    return namespace_manager.get_namespace(namespace)


def enable_namespace(namespace: str):
    return namespace_manager.enable_namespace(namespace)


def disable_namespace(namespace: str):
    return namespace_manager.disable_namespace(namespace)
