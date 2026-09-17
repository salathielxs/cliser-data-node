from __future__ import annotations

from fastapi import APIRouter, Depends

from api.auth import (
    AuthenticatedPrincipal,
    get_current_principal,
)

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["authentication"],
)


@router.get("/me")
async def auth_me(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    return {
        "authenticated": True,
        "identity_id": principal.identity_id,
        "role": principal.role,
        "namespace": principal.namespace,
        "credential_id": principal.credential_id,
    }
