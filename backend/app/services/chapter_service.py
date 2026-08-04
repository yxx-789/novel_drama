import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Chapter
from app.schemas.chapter import ChapterCreate, ChapterUpdate


async def create_chapter(
    db: AsyncSession,
    chapter_in: ChapterCreate,
    project_id: uuid.UUID,
) -> Chapter:
    chapter = Chapter(
        project_id=str(project_id),
        chapter_num=chapter_in.chapter_num,
        title=chapter_in.title,
        outline=chapter_in.outline,
        draft=chapter_in.draft,
        finalized_text=chapter_in.finalized_text,
        status=chapter_in.status,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def get_chapter_by_id(
    db: AsyncSession,
    chapter_id: uuid.UUID,
) -> Chapter | None:
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    return result.scalar_one_or_none()


async def list_chapters_by_project(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> list[Chapter]:
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == str(project_id))
        .order_by(Chapter.chapter_num.asc())
    )
    return list(result.scalars().all())


async def update_chapter(
    db: AsyncSession,
    chapter: Chapter,
    chapter_in: ChapterUpdate,
) -> Chapter:
    update_data = chapter_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def delete_chapter(db: AsyncSession, chapter: Chapter) -> None:
    await db.delete(chapter)
    await db.commit()
