from __future__ import annotations

from node.access_control import (
    AccessDenied,
    Principal,
    has_permission,
)
from node import namespace_manager


class NamespaceSecurityError(PermissionError):
    pass


def namespace_exists(namespace: str) -> bool:
    return namespace_manager.namespace_exists(namespace)


def namespace_is_active(namespace: str) -> bool:
    if not namespace_exists(namespace):
        return False

    ns = namespace_manager.get_namespace(namespace)

    return ns is not None and ns["status"] == "ACTIVE"


def check_namespace_scope(
    principal: Principal,
    namespace: str,
) -> bool:
    if not isinstance(namespace, str) or not namespace:
        return False

    if principal.role == "ADMIN":
        return True

    return principal.namespace == namespace


def require_namespace_access(
    principal: Principal,
    namespace: str,
    permission: str,
) -> None:

    if not namespace_exists(namespace):
        raise NamespaceSecurityError(
            f"Namespace inexistente: {namespace}"
        )

    if not namespace_is_active(namespace):
        raise NamespaceSecurityError(
            f"Namespace não está ativo: {namespace}"
        )

    if not check_namespace_scope(
        principal,
        namespace,
    ):
        raise AccessDenied(
            "Acesso fora do escopo do namespace: "
            f"identity={principal.identity_id} "
            f"principal_namespace={principal.namespace} "
            f"target_namespace={namespace}"
        )

    if not has_permission(
        principal,
        permission,
        namespace=namespace,
    ):
        raise AccessDenied(
            "Permissão insuficiente: "
            f"identity={principal.identity_id} "
            f"role={principal.role} "
            f"permission={permission}"
        )


def require_namespace_management(
    principal: Principal,
    namespace: str,
) -> None:
    """
    Autoriza operações de lifecycle do namespace.

    Permite gerenciamento tanto de namespaces ACTIVE
    quanto DISABLED. O namespace precisa existir,
    estar dentro do escopo da identidade e possuir
    a permissão namespace.manage.
    """

    if not namespace_exists(namespace):
        raise NamespaceSecurityError(
            f"Namespace inexistente: {namespace}"
        )

    if not check_namespace_scope(
        principal,
        namespace,
    ):
        raise AccessDenied(
            "Acesso fora do escopo do namespace: "
            f"identity={principal.identity_id} "
            f"principal_namespace={principal.namespace} "
            f"target_namespace={namespace}"
        )

    if not has_permission(
        principal,
        "namespace.manage",
        namespace=namespace,
    ):
        raise AccessDenied(
            "Permissão insuficiente: "
            f"identity={principal.identity_id} "
            f"role={principal.role} "
            f"permission=namespace.manage"
        )


def require_namespace_read(
    principal: Principal,
    namespace: str,
) -> None:
    require_namespace_access(
        principal,
        namespace,
        "namespace.read",
    )


def require_namespace_write(
    principal: Principal,
    namespace: str,
) -> None:
    require_namespace_access(
        principal,
        namespace,
        "object.create",
    )


def require_namespace_delete(
    principal: Principal,
    namespace: str,
) -> None:
    require_namespace_access(
        principal,
        namespace,
        "object.delete",
    )
