from __future__ import annotations

from dataclasses import dataclass


class AccessDenied(PermissionError):
    pass


ROLES = {
    "ADMIN",
    "OWNER",
    "WRITER",
    "READER",
}


PERMISSIONS = {
    "ADMIN": {
        "object.create",
        "object.read",
        "object.delete",
        "object.sign",
        "namespace.read",
        "namespace.manage",
        "quota.manage",
        "node.manage",
    },
    "OWNER": {
        "object.create",
        "object.read",
        "object.delete",
        "object.sign",
        "namespace.read",
        "namespace.manage",
        "quota.manage",
    },
    "WRITER": {
        "object.create",
        "object.read",
        "object.delete",
        "object.sign",
        "namespace.read",
    },
    "READER": {
        "object.read",
        "namespace.read",
    },
}


@dataclass(frozen=True)
class Principal:
    identity_id: str
    role: str
    namespace: str | None = None


def validate_role(role: str) -> str:
    if not isinstance(role, str):
        raise ValueError("role inválido.")

    role = role.upper()

    if role not in ROLES:
        raise ValueError(f"role desconhecido: {role}")

    return role


def create_principal(
    identity_id: str,
    role: str,
    namespace: str | None = None,
) -> Principal:

    if not isinstance(identity_id, str) or not identity_id:
        raise ValueError("identity_id inválido.")

    role = validate_role(role)

    if namespace is not None:
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace inválido.")

    return Principal(
        identity_id=identity_id,
        role=role,
        namespace=namespace,
    )


def has_permission(
    principal: Principal,
    permission: str,
    namespace: str | None = None,
) -> bool:

    if not isinstance(principal, Principal):
        raise TypeError("principal inválido.")

    if not isinstance(permission, str) or not permission:
        return False

    if namespace is not None:
        if principal.namespace is not None:
            if principal.namespace != namespace:
                return False

    return permission in PERMISSIONS[principal.role]


def require_permission(
    principal: Principal,
    permission: str,
    namespace: str | None = None,
) -> None:

    if not has_permission(
        principal,
        permission,
        namespace=namespace,
    ):
        raise AccessDenied(
            "Acesso negado: "
            f"identity={principal.identity_id} "
            f"role={principal.role} "
            f"permission={permission} "
            f"namespace={namespace}"
        )


def list_permissions(role: str) -> list[str]:
    role = validate_role(role)
    return sorted(PERMISSIONS[role])
