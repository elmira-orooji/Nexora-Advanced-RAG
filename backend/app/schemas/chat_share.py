import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class SharedSource(BaseModel):
    document_id: uuid.UUID | None = None
    title: str = Field(max_length=255)
    citation_id: int | None = None
    excerpt: str | None = Field(default=None, max_length=3000)
    page: int | None = None
    section: str | None = Field(default=None, max_length=255)
    ocr_provenance: dict[str, str] | None = None


class SharedMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12000)
    grounded: bool | None = None
    answer_basis: Literal["sources", "general", "hybrid"] | None = None
    sources: list[SharedSource] = Field(default_factory=list, max_length=12)


class ChatShareCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    visibility: Literal["team", "link"]
    expires_in_days: Literal[1, 7, 30] | None = None
    messages: list[SharedMessage] = Field(min_length=1, max_length=100)


class ChatShareCreated(BaseModel):
    id: uuid.UUID
    share_token: str
    visibility: str
    expires_at: datetime | None


class ChatShareView(BaseModel):
    id: uuid.UUID
    title: str
    owner_username: str
    visibility: str
    messages: list[SharedMessage]
    created_at: datetime
    expires_at: datetime | None


class ChatShareSummary(BaseModel):
    id: uuid.UUID
    title: str
    visibility: str
    expires_at: datetime | None
    created_at: datetime
