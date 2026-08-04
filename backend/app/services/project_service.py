import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


async def create_project(
    db: AsyncSession,
    project_in: ProjectCreate,
    owner_id: uuid.UUID,
) -> Project:
    project = Project(
        name=project_in.name,
        topic=project_in.topic,
        genre=project_in.genre,
        num_chapters=project_in.num_chapters,
        word_number=project_in.word_number,
        owner_id=str(owner_id),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def get_project_by_id(
    db: AsyncSession,
    project_id: uuid.UUID,
    owner_id: uuid.UUID | None = None,
) -> Project | None:
    filters = [Project.id == project_id]
    if owner_id is not None:
        filters.append(Project.owner_id == str(owner_id))
    result = await db.execute(select(Project).where(*filters))
    return result.scalar_one_or_none()


async def list_projects_by_owner(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == str(owner_id))
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


async def update_project(
    db: AsyncSession,
    project: Project,
    project_in: ProjectUpdate,
) -> Project:
    update_data = project_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    # 先删除关联的 tasks、drama_episodes（没有级联关系，需手动清理）
    from app.models.project import Task, DramaEpisode
    await db.execute(
        Task.__table__.delete().where(Task.project_id == str(project.id))
    )
    await db.execute(
        DramaEpisode.__table__.delete().where(DramaEpisode.project_id == str(project.id))
    )
    await db.delete(project)
    await db.commit()
