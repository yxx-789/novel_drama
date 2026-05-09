import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class ExportFormat(str, Enum):
    json = "json"
    md = "md"
    csv = "csv"


class DramaEpisodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    episode_num: int
    title: str | None
    source_chapters: str | None
    outline_json: dict | None
    script_json: dict | None
    status: str
    created_at: datetime
    updated_at: datetime
