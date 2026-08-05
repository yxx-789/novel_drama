import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectBase(BaseModel):
    name: str
    topic: str | None = None
    genre: str | None = None
    num_chapters: int = 0
    word_number: int = 0
    writing_config: dict | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    genre: str | None = None
    num_chapters: int | None = None
    word_number: int | None = None
    status: str | None = None
    writing_config: dict | None = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
