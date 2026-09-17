from __future__ import annotations

from typing import Any

from node.lifecycle import (
    garbage_collect_blocks,
    rebuild_references,
    lifecycle_status,
)


class LifecycleServiceError(Exception):
    pass


def garbage_collect() -> dict[str, Any]:
    try:
        return garbage_collect_blocks()

    except Exception as exc:
        raise LifecycleServiceError(
            str(exc)
        ) from exc


def rebuild_refcounts() -> dict[str, Any]:
    try:
        return rebuild_references()

    except Exception as exc:
        raise LifecycleServiceError(
            str(exc)
        ) from exc


def integrity_check() -> dict[str, Any]:
    try:
        return lifecycle_status()

    except Exception as exc:
        raise LifecycleServiceError(
            str(exc)
        ) from exc
