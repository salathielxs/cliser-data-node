from __future__ import annotations

from pydantic import BaseModel, Field


class NamespaceCreateRequest(BaseModel):
    namespace: str = Field(..., min_length=1, max_length=64)
    quota_bytes: int = Field(default=0, ge=0)


class NamespaceResponse(BaseModel):
    namespace: str
    status: str
    quota_bytes: int
    created_at: str
    updated_at: str


class NamespaceListResponse(BaseModel):
    items: list[NamespaceResponse]
    total: int
