from __future__ import annotations

from typing import Any

from node.metrics import storage_metrics


class MetricsServiceError(Exception):
    pass


def get_metrics() -> dict[str, Any]:
    try:
        return storage_metrics()
    except Exception as exc:
        raise MetricsServiceError(
            str(exc)
        ) from exc
