from __future__ import annotations

from pydantic import BaseModel


class ManifestBlockResponse(BaseModel):
    index: int
    block_id: str
    size: int


class ManifestResponse(BaseModel):
    object_id: str
    namespace: str
    total_size: int
    block_size: int
    block_count: int
    created_at: str
    status: str
    blocks: list[ManifestBlockResponse]
