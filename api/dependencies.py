from __future__ import annotations

from fastapi import Depends

from api.auth import (
    AuthenticatedPrincipal,
    get_current_principal,
)

from api.authorization import to_node_principal
from api.errors import APIError

from node.namespace_security import (
    NamespaceSecurityError,
    require_namespace_access,
    require_namespace_management,
)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

CurrentPrincipal = AuthenticatedPrincipal


async def current_principal(
    principal: AuthenticatedPrincipal = Depends(
        get_current_principal
    ),
) -> AuthenticatedPrincipal:
    """
    Retorna o principal autenticado da requisição.
    """
    return principal


# ---------------------------------------------------------------------------
# Generic authorization
# ---------------------------------------------------------------------------

def require_permission(permission: str):
    """
    Dependência HTTP reutilizável para autorização global.

    A matriz de permissões permanece no node.access_control.
    """
    from api.authorization import require_api_permission

    return require_api_permission(permission)


# ---------------------------------------------------------------------------
# Namespace authorization
# ---------------------------------------------------------------------------

def require_namespace_permission(permission: str):
    """
    Autoriza uma operação dentro de um namespace específico.

    O namespace alvo é recebido pela rota através do parâmetro
    chamado 'namespace'.

    A política de domínio permanece em:
        node.namespace_security
        node.access_control
    """

    async def dependency(
        namespace: str,
        principal: AuthenticatedPrincipal = Depends(
            get_current_principal
        ),
    ) -> AuthenticatedPrincipal:

        node_principal = to_node_principal(principal)

        try:
            require_namespace_access(
                node_principal,
                namespace,
                permission,
            )

        except NamespaceSecurityError as exc:
            message = str(exc)

            if message.startswith("Namespace inexistente:"):
                raise APIError(
                    code="NAMESPACE_NOT_FOUND",
                    message=f"Namespace não encontrado: {namespace}",
                    status_code=404,
                    details={
                        "namespace": namespace,
                    },
                ) from exc

            raise APIError(
                code="NAMESPACE_ACCESS_DENIED",
                message=message,
                status_code=403,
                details={
                    "namespace": namespace,
                    "permission": permission,
                },
            ) from exc

        except Exception as exc:
            from node.access_control import AccessDenied

            if isinstance(exc, AccessDenied):
                raise APIError(
                    code="AUTHZ_DENIED",
                    message="Access denied",
                    status_code=403,
                    details={
                        "namespace": namespace,
                        "permission": permission,
                        "identity_id": principal.identity_id,
                        "role": principal.role,
                    },
                ) from exc

            raise

        return principal

    return dependency


# ---------------------------------------------------------------------------
# Namespace lifecycle management
# ---------------------------------------------------------------------------

def require_namespace_management_permission():
    """
    Dependência HTTP para operações administrativas de lifecycle.

    Permite gerenciamento de namespaces ACTIVE ou DISABLED.
    A política de domínio permanece em node.namespace_security.
    """

    async def dependency(
        namespace: str,
        principal: AuthenticatedPrincipal = Depends(
            get_current_principal
        ),
    ) -> AuthenticatedPrincipal:

        node_principal = to_node_principal(principal)

        try:
            require_namespace_management(
                node_principal,
                namespace,
            )

        except NamespaceSecurityError as exc:
            message = str(exc)

            if message.startswith("Namespace inexistente:"):
                raise APIError(
                    code="NAMESPACE_NOT_FOUND",
                    message=f"Namespace não encontrado: {namespace}",
                    status_code=404,
                    details={
                        "namespace": namespace,
                    },
                ) from exc

            raise APIError(
                code="NAMESPACE_ACCESS_DENIED",
                message=message,
                status_code=403,
                details={
                    "namespace": namespace,
                    "permission": "namespace.manage",
                },
            ) from exc

        except Exception as exc:
            from node.access_control import AccessDenied

            if isinstance(exc, AccessDenied):
                raise APIError(
                    code="AUTHZ_DENIED",
                    message="Access denied",
                    status_code=403,
                    details={
                        "namespace": namespace,
                        "permission": "namespace.manage",
                        "identity_id": principal.identity_id,
                        "role": principal.role,
                    },
                ) from exc

            raise

        return principal

    return dependency


# ---------------------------------------------------------------------------
# Future dependency composition
# ---------------------------------------------------------------------------
#
# Próximas políticas poderão ser adicionadas aqui:
#
# - quota_check(...)
# - request_limits(...)
# - idempotency(...)
# - transaction_context(...)
# - lifecycle_guard(...)
# - object_access(...)
#
# A API apenas compõe as políticas.
# As regras de domínio continuam em node/*.
# ---------------------------------------------------------------------------
