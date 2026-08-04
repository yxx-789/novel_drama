import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.schemas.chapter import ChapterCreate, ChapterOut, ChapterUpdate
from app.schemas.drama import ExportFormat
from app.services.chapter_service import (
    create_chapter,
    delete_chapter,
    get_chapter_by_id,
    list_chapters_by_project,
    update_chapter,
)
from app.services.project_service import get_project_by_id
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(
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
    chapters = await list_chapters_by_project(db, project_id)
    return chapters


@router.post("/projects/{project_id}/chapters", response_model=ChapterOut, status_code=status.HTTP_201_CREATED)
async def create_new_chapter(
    project_id: uuid.UUID,
    chapter_in: ChapterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    chapter = await create_chapter(db, chapter_in, project_id)
    return chapter


@router.get("/chapters/{chapter_id}", response_model=ChapterOut)
async def get_chapter(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chapter = await get_chapter_by_id(db, chapter_id)
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )
    project = await get_project_by_id(db, uuid.UUID(str(chapter.project_id)), current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    return chapter


@router.put("/chapters/{chapter_id}", response_model=ChapterOut)
async def update_existing_chapter(
    chapter_id: uuid.UUID,
    chapter_in: ChapterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chapter = await get_chapter_by_id(db, chapter_id)
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )
    project = await get_project_by_id(db, uuid.UUID(str(chapter.project_id)), current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    updated = await update_chapter(db, chapter, chapter_in)
    return updated


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_chapter(
    chapter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chapter = await get_chapter_by_id(db, chapter_id)
    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="章节不存在",
        )
    project = await get_project_by_id(db, uuid.UUID(str(chapter.project_id)), current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    await delete_chapter(db, chapter)
    return None


@router.get("/projects/{project_id}/chapters/export")
async def export_chapters(
    project_id: uuid.UUID,
    format: ExportFormat = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在或无权限访问",
        )
    chapters = await list_chapters_by_project(db, project_id)
    if not chapters:
        raise HTTPException(status_code=404, detail="暂无章节可导出")

    lines = [f"# {project.name}", ""]
    for ch in chapters:
        lines.append(f"## 第{ch.chapter_num}章 {ch.title or ''}")
        lines.append("")
        if ch.finalized_text:
            lines.append(ch.finalized_text)
        elif ch.draft:
            lines.append(ch.draft)
        elif ch.outline:
            lines.append(ch.outline)
        lines.append("")

    content = "\n\n".join(lines)
    if format.value == "json":
        content = json.dumps(
            [{"chapter_num": c.chapter_num, "title": c.title, "content": c.finalized_text or c.draft or c.outline} for c in chapters],
            ensure_ascii=False, indent=2
        )
        media_type = "application/json"
        ext = "json"
    else:
        media_type = "text/markdown; charset=utf-8"
        ext = "md"

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="chapters.{ext}"'},
    )


@router.post("/chapters/export/batch")
async def export_chapters_batch(
    payload: dict,
    format: ExportFormat = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量导出选中章节为 MD / JSON"""
    chapter_ids = payload.get("chapter_ids", [])
    if not chapter_ids:
        raise HTTPException(status_code=400, detail="未选择章节")

    from app.models.project import Chapter as ChapterModel
    chapter_ids_uuid = [uuid.UUID(ch_id) for ch_id in chapter_ids]
    result = await db.execute(
        select(ChapterModel).where(ChapterModel.id.in_(chapter_ids_uuid)).order_by(ChapterModel.chapter_num)
    )
    chapters = list(result.scalars().all())
    if not chapters:
        raise HTTPException(status_code=404, detail="未找到选中的章节")

    # 校验权限（取第一个章节所属项目）
    project = await get_project_by_id(db, uuid.UUID(str(chapters[0].project_id)), current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")

    lines = [f"# {project.name}", ""]
    for ch in chapters:
        lines.append(f"## 第{ch.chapter_num}章 {ch.title or ''}")
        lines.append("")
        if ch.finalized_text:
            lines.append(ch.finalized_text)
        elif ch.draft:
            lines.append(ch.draft)
        elif ch.outline:
            lines.append(ch.outline)
        lines.append("")

    content = "\n\n".join(lines)
    if format.value == "json":
        content = json.dumps(
            [{"chapter_num": c.chapter_num, "title": c.title, "content": c.finalized_text or c.draft or c.outline} for c in chapters],
            ensure_ascii=False, indent=2
        )
        media_type = "application/json"
        ext = "json"
    else:
        media_type = "text/markdown; charset=utf-8"
        ext = "md"

    return StreamingResponse(
        iter([content.encode("utf-8")]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="chapters_batch.{ext}"'},
    )