import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterBase(BaseModel):
    chapter_num: int
    title: str | None = None
    outline: str | None = None
    draft: str | None = None
    finalized_text: str | None = None
    status: str = "pending"


class ChapterCreate(ChapterBase):
    pass


class ChapterUpdate(BaseModel):
    chapter_num: int | None = None
    title: str | None = None
    outline: str | None = None
    draft: str | None = None
    finalized_text: str | None = None
    status: str | None = None


class ChapterOut(ChapterBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
