import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.task import TaskOut
from app.services.project_service import get_project_by_id
from app.services.task_service import (
    create_task,
    run_architecture_task,
    run_chapter_task,
    run_directory_task,
    run_drama_episode_task,
    run_drama_plan_task,
)

router = APIRouter()


@router.post("/projects/{project_id}/generate/architecture", response_model=TaskOut)
async def trigger_architecture_generation(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(
        db, project_id, "architecture", params={"project_id": str(project_id)}
    )
    asyncio.create_task(run_architecture_task(task.id))
    return task


@router.post("/projects/{project_id}/generate/directory", response_model=TaskOut)
async def trigger_directory_generation(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(db, project_id, "directory", params={"project_id": str(project_id)})
    asyncio.create_task(run_directory_task(task.id))
    return task


@router.post("/projects/{project_id}/generate/chapter/{chapter_num}", response_model=TaskOut)
async def trigger_chapter_generation(
    project_id: uuid.UUID,
    chapter_num: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(
        db, project_id, "chapter", params={"project_id": str(project_id), "chapter_num": chapter_num}
    )
    asyncio.create_task(run_chapter_task(task.id))
    return task


@router.post("/projects/{project_id}/generate/drama-plan", response_model=TaskOut)
async def trigger_drama_plan_generation(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(
        db, project_id, "drama_plan", params={"project_id": str(project_id)}
    )
    asyncio.create_task(run_drama_plan_task(task.id))
    return task


@router.post("/projects/{project_id}/generate/drama-episode/{episode_num}", response_model=TaskOut)
async def trigger_drama_episode_generation(
    project_id: uuid.UUID,
    episode_num: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(
        db, project_id, "drama_episode", params={"project_id": str(project_id), "episode_num": episode_num}
    )
    asyncio.create_task(run_drama_episode_task(task.id))
    return task
