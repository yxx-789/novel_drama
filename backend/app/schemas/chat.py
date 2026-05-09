import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    model_name: str | None
    tokens_used: int | None
    meta_json: dict | None
    created_at: datetime
    updated_at: datetime


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    user_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatSessionDetailOut(ChatSessionOut):
    messages: list[ChatMessageOut]


class ChatMessageCreate(BaseModel):
    content: str


class ChatSessionCreate(BaseModel):
    project_id: uuid.UUID | None = None
    title: str | None = None
