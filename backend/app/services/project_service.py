import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.generator.block_library import (
    ConfigHardConflictError,
    roll_internal_flavor,
    validate_writing_config,
)
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


async def create_project(
    db: AsyncSession,
    project_in: ProjectCreate,
    owner_id: uuid.UUID,
) -> Project:
    # C2：创建时校验写作配置——在掷内部风味之前，用 validate_writing_config 校验用户原始选择的
    # writing_config（不含 internal_flavor）。内部风味是系统自动配的、天然兼容，不参与创建拦截；
    # plot_direction 等用户输入字段已含在 writing_config 中，规则正常触发。
    # 硬冲突 → ConfigHardConflictError，由 router 转 400；软警告不阻断，仅记日志；
    # 无 writing_config（旧项目）跳过。
    if project_in.writing_config:
        conflict = validate_writing_config(project_in.writing_config)
        if conflict["hard"]:
            raise ConfigHardConflictError(
                f"写作配置存在冲突：{'；'.join(conflict['hard'])}"
            )
        if conflict["soft"]:
            logger.info(
                "create_project: writing config soft warnings (project=%s): %s",
                project_in.name,
                "；".join(conflict["soft"]),
            )
    # C1：接入内部风味层——对传入的 writing_config 掷一组内部风味，写回 internal_flavor 键，
    # 使 build_context 能渲染「内部风味」段。writing_config 可能为 None，rolling 前先转为 dict。
    if project_in.writing_config:
        config = dict(project_in.writing_config)
        config = roll_internal_flavor(config)
    else:
        config = None
    project = Project(
        name=project_in.name,
        topic=project_in.topic,
        genre=project_in.genre,
        num_chapters=project_in.num_chapters,
        word_number=project_in.word_number,
        story_shape=project_in.story_shape,
        total_chapters_target=project_in.total_chapters_target,
        writing_config=config,
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

    # 全书目标章数创建后不可修改：已锁定 M 的项目，传入了不同的 M → 拒绝
    if "total_chapters_target" in update_data:
        new_m = update_data["total_chapters_target"]
        if project.total_chapters_target is not None and new_m != project.total_chapters_target:
            raise ValueError("全书目标章数创建后不可修改")
        if new_m is not None and not (10 <= new_m <= 1000):
            raise ValueError("全书目标总章数需在 10~1000 之间")

    # 形态切换规则：open→final 自动清空 M；final→open 必须补传 M
    new_shape = update_data.get("story_shape")
    if new_shape is not None and new_shape != project.story_shape:
        if new_shape not in ("final", "open"):
            raise ValueError("故事形态取值非法：final / open")
        if new_shape == "final":
            update_data["total_chapters_target"] = None
        elif project.story_shape == "final":
            if not update_data.get("total_chapters_target"):
                raise ValueError("切换为连载开篇时必须提供全书目标总章数")

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
