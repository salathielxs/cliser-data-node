from __future__ import annotations

from fastapi import Depends

from api.auth import (
    AuthenticatedPrincipal,
    get_current_principal,
)

from api.errors import APIError

from node.access_control import (
    AccessDenied,
    Principal,
    require_permission,
)


def to_node_principal(
    principal: AuthenticatedPrincipal,
) -> Principal:
    return Principal(
        identity_id=principal.identity_id,
        role=principal.role,
        namespace=principal.namespace,
    )


def require_api_permission(permission: str):
    async def dependency(
        principal: AuthenticatedPrincipal = Depends(
            get_current_principal
        ),
    ) -> AuthenticatedPrincipal:

        node_principal = to_node_principal(principal)

        try:
            require_permission(
                node_principal,
                permission,
                namespace=principal.namespace,
            )

        except AccessDenied as exc:
            raise APIError(
                code="AUTHZ_DENIED",
                message="Access denied",
                status_code=403,
                details={
                    "permission": permission,
                    "identity_id": principal.identity_id,
                    "role": principal.role,
                    "namespace": principal.namespace,
                },
            ) from exc

        return principal

    return dependency
