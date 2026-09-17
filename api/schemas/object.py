from pydantic import BaseModel, Field
from typing import Optional


class ObjectCreateRequest(BaseModel):
    data: str = Field(..., min_length=1)


class ObjectCreateResponse(BaseModel):
    object_id: str
    namespace: str
    size: int
    content_hash: str
    status: str


class ObjectMetadataResponse(BaseModel):
    object_id: str
    namespace: str
    size: int
    content_hash: str
    created_at: Optional[str] = None
    status: str


class ObjectVerifyResponse(BaseModel):
    object_id: str
    valid: bool
    status: str
    message: str


class ObjectDeleteResponse(BaseModel):
    object_id: str
    deleted: bool
    status: str


class ObjectListItem(BaseModel):
    object_id: str
    namespace: str
    size: int
    created_at: Optional[str] = None
    status: str


class ObjectListResponse(BaseModel):
    namespace: str
    objects: list[ObjectListItem]
    count: int
