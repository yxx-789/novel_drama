import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

SHAPE_VALUES = ("final", "open")


class ProjectBase(BaseModel):
    name: str
    topic: str | None = None
    genre: str | None = None
    num_chapters: int = 0
    word_number: int = 0
    writing_config: dict | None = None
    story_shape: str


class ProjectCreate(ProjectBase):
    total_chapters_target: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self):
        if self.story_shape not in SHAPE_VALUES:
            raise ValueError("故事形态取值非法：final（短篇完结）/ open（连载开篇）")
        if self.story_shape == "open":
            m = self.total_chapters_target
            if m is None:
                raise ValueError("连载开篇必须提供全书目标总章数 total_chapters_target")
            if not (10 <= m <= 1000):
                raise ValueError("全书目标总章数需在 10~1000 之间")
            if m <= self.num_chapters:
                raise ValueError("全书目标总章数必须大于当前章节数")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    genre: str | None = None
    num_chapters: int | None = None
    word_number: int | None = None
    status: str | None = None
    writing_config: dict | None = None
    story_shape: str | None = None
    total_chapters_target: int | None = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    total_chapters_target: int | None = None
