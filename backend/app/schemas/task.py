import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    task_type: str
    params: dict | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    task_type: str
    status: str
    params: dict | None
    result: dict | None
    progress: int
    error_msg: str | None
    created_at: datetime
    updated_at: datetime
