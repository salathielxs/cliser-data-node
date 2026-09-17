from __future__ import annotations

from pydantic import BaseModel, Field


class QuotaResponse(BaseModel):
    namespace: str
    quota_bytes: int
    used_bytes: int
    available_bytes: int | None = None


class QuotaUpdateRequest(BaseModel):
    quota_bytes: int = Field(ge=0)
    mode: str = "LOGICAL"
