from __future__ import annotations

from pydantic import BaseModel


class TransactionResponse(BaseModel):
    transaction_id: str
    object_id: str | None = None
    namespace: str | None = None
    operation: str
    state: str
    created_at: str
    updated_at: str


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    count: int
