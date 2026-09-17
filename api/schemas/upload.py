from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    object_id: str
    namespace: str
    filename: str
    size: int
    content_hash: str
    status: str
