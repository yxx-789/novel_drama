import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator.block_library import ConfigHardConflictError
from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.project_service import (
    create_project,
    delete_project,
    get_project_by_id,
    list_projects_by_owner,
    update_project,
)
from sqlalchemy import select
from app.models.project import Chapter, ProjectAsset, DramaEpisode
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = await list_projects_by_owner(db, current_user.id)
    return projects


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_new_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        project = await create_project(db, project_in, current_user.id)
    except ConfigHardConflictError as e:
        # 写作配置存在硬冲突 → 400，detail 即服务层给出的冲突文案
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ValueError as e:
        # 形态等防御性 ValueError → 400（pydantic 形态校验已在 schema 层返回 422）
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return project


@router.get("/{project_id}/export")
async def export_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出整个项目为一个 Markdown 文件"""
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )

    lines = []
    lines.append(f"# {project.name}")
    lines.append("")
    if project.topic:
        lines.append(f"> 主题：{project.topic}")
    if project.genre:
        lines.append(f"> 类型：{project.genre}")
    lines.append(f"> 章节数：{project.num_chapters}")
    lines.append("")

    # Assets
    result = await db.execute(
        select(ProjectAsset).where(ProjectAsset.project_id == str(project_id))
    )
    assets = {a.asset_type: a.content_text or "" for a in result.scalars().all()}

    if assets.get("architecture"):
        lines.append("## 世界观架构")
        lines.append("")
        lines.append(assets["architecture"])
        lines.append("")

    if assets.get("characters"):
        lines.append("## 人物设定")
        lines.append("")
        lines.append(assets["characters"])
        lines.append("")

    if assets.get("directory"):
        lines.append("## 章节目录")
        lines.append("")
        lines.append(assets["directory"])
        lines.append("")

    # Chapters
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == str(project_id)).order_by(Chapter.chapter_num)
    )
    chapters = list(result.scalars().all())
    if chapters:
        lines.append("## 章节正文")
        lines.append("")
        for ch in chapters:
            lines.append(f"### 第{ch.chapter_num}章 {ch.title or ''}")
            lines.append("")
            if ch.finalized_text:
                lines.append(ch.finalized_text)
            elif ch.draft:
                lines.append(ch.draft)
            elif ch.outline:
                lines.append(ch.outline)
            lines.append("")

    # Drama plan
    if assets.get("drama_plan"):
        lines.append("## 短剧改编计划")
        lines.append("")
        lines.append(assets["drama_plan"])
        lines.append("")

    # Drama episodes
    result = await db.execute(
        select(DramaEpisode).where(DramaEpisode.project_id == str(project_id)).order_by(DramaEpisode.episode_num)
    )
    episodes = list(result.scalars().all())
    if episodes:
        lines.append("## 短剧脚本")
        lines.append("")
        for ep in episodes:
            lines.append(f"### 第{ep.episode_num}集 {ep.title or ''}")
            lines.append("")
            if ep.script_json:
                import json
                lines.append(json.dumps(ep.script_json, ensure_ascii=False, indent=2))
            elif ep.outline_json:
                import json
                lines.append(json.dumps(ep.outline_json, ensure_ascii=False, indent=2))
            lines.append("")

    content = "\n".join(lines)
    filename = f"{project.name.replace(' ', '_').replace('/', '_')}_export.md"
    # RFC 5987: ascii fallback + utf-8 encoded filename*
    content_disposition = (
        f"attachment; filename=\"project_export.md\"; filename*=UTF-8''{quote(filename, safe='')}"
    )

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": content_disposition},
    )


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    return project


@router.put("/{project_id}", response_model=ProjectOut)
async def update_existing_project(
    project_id: uuid.UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    try:
        updated = await update_project(db, project, project_in)
    except ValueError as e:
        # M 锁定 / 形态转换规则违反 → 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    await delete_project(db, project)
    return None
