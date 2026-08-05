import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.preset_categories import get_preset_category_names
from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.services.inspiration_service import get_hot_notes, import_inspiration
from app.services.project_service import get_project_by_id

router = APIRouter()


@router.get("/inspiration/categories")
async def list_categories(
    current_user: User = Depends(get_current_user),
):
    return get_preset_category_names()


@router.get("/inspiration/hot")
async def list_hot_notes(
    category: str | None = None,
    keyword: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_hot_notes(db, category=category, keyword=keyword, limit=limit)


@router.post("/projects/{project_id}/inspiration")
async def import_note(
    project_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    project = await import_inspiration(db, project, payload)
    return {"success": True, "topic": project.topic}
