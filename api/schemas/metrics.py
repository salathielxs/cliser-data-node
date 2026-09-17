from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    objects: dict[str, Any]
    direct: dict[str, Any]
    block_objects: dict[str, Any]
    blocks: dict[str, Any]
    deduplication: dict[str, Any]
    capacity: dict[str, Any]
