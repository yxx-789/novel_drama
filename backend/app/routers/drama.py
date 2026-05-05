import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.project import DramaEpisode
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.drama import DramaEpisodeOut
from app.services.project_service import get_project_by_id

router = APIRouter()


@router.get("/projects/{project_id}/drama-episodes", response_model=list[DramaEpisodeOut])
async def list_drama_episodes(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    result = await db.execute(
        select(DramaEpisode)
        .where(DramaEpisode.project_id == str(project_id))
        .order_by(DramaEpisode.episode_num)
    )
    return list(result.scalars().all())
