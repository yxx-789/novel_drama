import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.task import TaskOut
from app.services.project_service import get_project_by_id
from app.services.task_service import create_task
from app.worker.tasks import (
    run_architecture,
    run_batch_chapters,
    run_chapter,
    run_directory,
    run_drama_batch,
    run_drama_episode,
    run_drama_plan,
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
    run_architecture.delay(str(task.id))
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
    run_directory.delay(str(task.id))
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
    run_chapter.delay(str(task.id))
    return task


@router.post("/projects/{project_id}/generate/chapters/batch", response_model=TaskOut)
async def trigger_batch_chapters_generation(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(
        db, project_id, "batch_chapters", params={"project_id": str(project_id)}
    )
    run_batch_chapters.delay(str(task.id))
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
    run_drama_plan.delay(str(task.id))
    return task


@router.post("/projects/{project_id}/generate/drama-episode/{episode_num}", response_model=TaskOut)
async def trigger_drama_episode_generation(
    project_id: uuid.UUID,
    episode_num: int,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    params = {"project_id": str(project_id), "episode_num": episode_num}
    chapter_nums = payload.get("chapter_nums")
    if chapter_nums:
        params["chapter_nums"] = chapter_nums
    task = await create_task(
        db, project_id, "drama_episode", params=params
    )
    run_drama_episode.delay(str(task.id))
    return task


@router.post("/projects/{project_id}/generate/drama-batch", response_model=TaskOut)
async def trigger_drama_batch_generation(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(
        db, project_id, "drama_batch", params={"project_id": str(project_id)}
    )
    run_drama_batch.delay(str(task.id))
    return task
