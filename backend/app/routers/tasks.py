import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.task import TaskCreate, TaskOut
from app.services.project_service import get_project_by_id
from app.services.task_service import create_task, get_task_by_id, list_tasks_by_project, update_task_status

router = APIRouter()


@router.post("/projects/{project_id}/tasks", response_model=TaskOut)
async def create_task_endpoint(
    project_id: uuid.UUID,
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    task = await create_task(db, project_id, task_in.task_type, task_in.params)
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[TaskOut])
async def list_tasks_endpoint(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    tasks = await list_tasks_by_project(db, project_id)
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    project = await get_project_by_id(db, uuid.UUID(str(task.project_id)), current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_task_endpoint(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    project = await get_project_by_id(db, uuid.UUID(str(task.project_id)), current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

    if task.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status}，不可取消")

    # Revoke Celery task
    celery_app.control.revoke(str(task_id), terminate=True, signal="SIGTERM")

    # Update DB status
    await update_task_status(db, task_id, "failed", error_msg="用户取消")
    return {"message": "任务已取消", "task_id": str(task_id)}
