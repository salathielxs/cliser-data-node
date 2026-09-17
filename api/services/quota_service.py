from __future__ import annotations

from typing import Any

from node.quota import (
    QUOTA_MODES,
    get_quota as node_get_quota,
    quota_status,
    set_quota as node_set_quota,
)


class QuotaServiceError(Exception):
    pass


def _validate_mode(mode: str) -> str:
    normalized = mode.upper()

    if normalized not in QUOTA_MODES:
        raise QuotaServiceError(
            f"Modo de quota inválido: {normalized}. "
            f"Use: {', '.join(sorted(QUOTA_MODES))}"
        )

    return normalized


def get_quota(
    namespace: str,
    mode: str = "LOGICAL",
) -> dict[str, Any]:
    if not namespace:
        raise QuotaServiceError("Namespace inválido")

    mode = _validate_mode(mode)

    quota = node_get_quota(namespace)

    if quota is None:
        raise QuotaServiceError(
            "Quota não configurada"
        )

    status = quota_status(
        namespace,
        mode=mode,
    )

    return {
        "namespace": status["namespace"],
        "quota_bytes": status["quota_bytes"],
        "used_bytes": status["used_bytes"],
        "available_bytes": status["available_bytes"],
    }


def set_quota(
    namespace: str,
    quota_bytes: int,
    mode: str = "LOGICAL",
) -> dict[str, Any]:
    if not namespace:
        raise QuotaServiceError("Namespace inválido")

    mode = _validate_mode(mode)

    try:
        node_set_quota(
            namespace,
            quota_bytes,
        )
    except ValueError as exc:
        raise QuotaServiceError(
            str(exc)
        ) from exc

    return get_quota(
        namespace,
        mode=mode,
    )
