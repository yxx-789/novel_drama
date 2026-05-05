from pydantic import BaseModel
from datetime import datetime


class DramaEpisodeOut(BaseModel):
    id: str
    project_id: str
    episode_num: int
    title: str | None
    source_chapters: str | None
    outline_json: dict | None
    script_json: dict | None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
