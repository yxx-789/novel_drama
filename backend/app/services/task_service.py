import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import AsyncSessionLocal
from app.models.project import Project, ProjectAsset, Task
from app.services.generation_service import (
    generate_architecture,
    generate_chapter_draft,
    generate_directory,
    parse_chapter_blueprint,
)
from app.services.project_service import get_project_by_id

logger = logging.getLogger(__name__)


async def create_task(db: AsyncSession, project_id: uuid.UUID, task_type: str, params: dict | None = None) -> Task:
    task = Task(
        project_id=str(project_id),
        task_type=task_type,
        status="pending",
        params=params,
        progress=0,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task_by_id(db: AsyncSession, task_id: uuid.UUID) -> Task | None:
    result = await db.execute(select(Task).where(Task.id == str(task_id)))
    return result.scalar_one_or_none()


async def list_tasks_by_project(db: AsyncSession, project_id: uuid.UUID) -> list[Task]:
    result = await db.execute(
        select(Task).where(Task.project_id == str(project_id)).order_by(Task.created_at.desc())
    )
    return list(result.scalars().all())


async def update_task_status(
    db: AsyncSession,
    task_id: uuid.UUID,
    status: str,
    progress: int | None = None,
    result: dict | None = None,
    error_msg: str | None = None,
) -> Task | None:
    task = await get_task_by_id(db, task_id)
    if not task:
        return None
    task.status = status
    if progress is not None:
        task.progress = progress
    if result is not None:
        task.result = result
    if error_msg is not None:
        task.error_msg = error_msg
    await db.commit()
    await db.refresh(task)
    return task


async def _save_asset(db: AsyncSession, project_id: str, asset_type: str, content_text: str) -> None:
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_text = content_text
        asset.version += 1
    else:
        asset = ProjectAsset(
            project_id=project_id,
            asset_type=asset_type,
            content_text=content_text,
        )
        db.add(asset)
    await db.commit()


async def run_architecture_task(task_id: uuid.UUID) -> None:
    """
    后台执行 architecture 生成任务。
    使用独立的数据库 session。
    """
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=10)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            user_guidance = ""
            if task.params and isinstance(task.params, dict):
                user_guidance = task.params.get("user_guidance", "")

            await update_task_status(db, task_id, "running", progress=30)
            architecture_text, character_state_text = await generate_architecture(
                project, user_guidance=user_guidance
            )

            await update_task_status(db, task_id, "running", progress=70)
            await _save_asset(db, str(task.project_id), "architecture", architecture_text)
            await _save_asset(db, str(task.project_id), "characters", character_state_text)

            await update_task_status(
                db,
                task_id,
                "success",
                progress=100,
                result={"architecture_saved": True, "character_state_saved": True},
            )
            logger.info(f"Architecture task {task_id} completed successfully")
        except Exception as e:
            logger.exception(f"Architecture task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass


async def _get_asset_text(db: AsyncSession, project_id: str, asset_type: str) -> str | None:
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    return asset.content_text if asset else None


async def _ensure_chapters(db: AsyncSession, project_id: str, parsed_chapters: list[dict]) -> None:
    """根据解析的目录，初始化 chapters 表记录（如果不存在）"""
    from app.models.project import Chapter
    for ch in parsed_chapters:
        num = ch["chapter_number"]
        result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_num == num,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            chapter = Chapter(
                project_id=project_id,
                chapter_num=num,
                title=ch["chapter_title"] or f"第{num}章",
                outline=ch["chapter_summary"] or "",
                status="draft",
            )
            db.add(chapter)
    await db.commit()


async def run_directory_task(task_id: uuid.UUID) -> None:
    """后台执行 directory 生成任务"""
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=10)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            user_guidance = ""
            if task.params and isinstance(task.params, dict):
                user_guidance = task.params.get("user_guidance", "")

            await update_task_status(db, task_id, "running", progress=40)
            directory_text, parsed_chapters = await generate_directory(
                project, architecture_text=architecture_text, user_guidance=user_guidance
            )

            await update_task_status(db, task_id, "running", progress=70)
            await _save_asset(db, str(task.project_id), "directory", directory_text)
            await _ensure_chapters(db, str(task.project_id), parsed_chapters)

            await update_task_status(
                db,
                task_id,
                "success",
                progress=100,
                result={"directory_saved": True, "chapters_created": len(parsed_chapters)},
            )
            logger.info(f"Directory task {task_id} completed successfully")
        except Exception as e:
            logger.exception(f"Directory task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass


async def run_chapter_task(task_id: uuid.UUID) -> None:
    """后台执行单章正文生成任务"""
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=10)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            chapter_num = 1
            if task.params and isinstance(task.params, dict):
                chapter_num = task.params.get("chapter_num", 1)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            directory_text = await _get_asset_text(db, str(task.project_id), "directory")
            if not directory_text:
                raise RuntimeError("Directory not found. Please generate directory first.")

            await update_task_status(db, task_id, "running", progress=30)

            previous_draft = None
            if chapter_num > 1:
                from app.models.project import Chapter
                result = await db.execute(
                    select(Chapter).where(
                        Chapter.project_id == str(task.project_id),
                        Chapter.chapter_num == chapter_num - 1,
                    )
                )
                prev_chapter = result.scalar_one_or_none()
                if prev_chapter:
                    previous_draft = prev_chapter.draft

            await update_task_status(db, task_id, "running", progress=50)
            draft_text = await generate_chapter_draft(
                project,
                chapter_num=chapter_num,
                architecture_text=architecture_text,
                directory_text=directory_text,
                previous_chapter_draft=previous_draft,
            )

            await update_task_status(db, task_id, "running", progress=80)

            from app.models.project import Chapter
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                    Chapter.chapter_num == chapter_num,
                )
            )
            chapter = result.scalar_one_or_none()
            if chapter:
                chapter.draft = draft_text
                chapter.status = "draft_generated"
            else:
                parsed_chapters = parse_chapter_blueprint(directory_text)
                ch_info = None
                for ch in parsed_chapters:
                    if ch["chapter_number"] == chapter_num:
                        ch_info = ch
                        break
                chapter = Chapter(
                    project_id=str(task.project_id),
                    chapter_num=chapter_num,
                    title=ch_info["chapter_title"] if ch_info else f"第{chapter_num}章",
                    outline=ch_info["chapter_summary"] if ch_info else "",
                    draft=draft_text,
                    status="draft_generated",
                )
                db.add(chapter)
            await db.commit()

            await update_task_status(
                db,
                task_id,
                "success",
                progress=100,
                result={"chapter_num": chapter_num, "draft_saved": True},
            )
            logger.info(f"Chapter task {task_id} completed successfully")
        except Exception as e:
            logger.exception(f"Chapter task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass


async def _ensure_drama_episodes(db: AsyncSession, project_id: str, episodes: list[dict]) -> None:
    """根据改编计划初始化 drama_episodes 表记录"""
    from app.models.project import DramaEpisode
    for ep in episodes:
        num = ep["episode_num"]
        result = await db.execute(
            select(DramaEpisode).where(
                DramaEpisode.project_id == project_id,
                DramaEpisode.episode_num == num,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            episode = DramaEpisode(
                project_id=project_id,
                episode_num=num,
                title=ep.get("title", f"第{num}集"),
                source_chapters=ep.get("source_chapters", ""),
                status="pending",
            )
            db.add(episode)
    await db.commit()


async def run_drama_plan_task(task_id: uuid.UUID) -> None:
    """后台执行短剧改编计划生成任务（桩）"""
    import asyncio

    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=10)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            await update_task_status(db, task_id, "running", progress=30)

            # Stub: 模拟章节到剧集的分组（每 3 章一集）
            num_chapters = project.num_chapters or 10
            chapters_per_episode = 3
            episodes = []
            for i in range(1, num_chapters + 1, chapters_per_episode):
                end = min(i + chapters_per_episode - 1, num_chapters)
                episodes.append({
                    "episode_num": (i - 1) // chapters_per_episode + 1,
                    "title": f"第{(i - 1) // chapters_per_episode + 1}集",
                    "source_chapters": f"第{i}-{end}章" if i != end else f"第{i}章",
                })

            await update_task_status(db, task_id, "running", progress=60)
            await _ensure_drama_episodes(db, str(task.project_id), episodes)

            await update_task_status(
                db,
                task_id,
                "success",
                progress=100,
                result={"episodes_created": len(episodes)},
            )
            logger.info(f"Drama plan task {task_id} completed successfully")
        except Exception as e:
            logger.exception(f"Drama plan task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass


async def run_drama_episode_task(task_id: uuid.UUID) -> None:
    """后台执行单集短剧脚本生成任务（桩）"""
    import asyncio

    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=10)

            episode_num = 1
            if task.params and isinstance(task.params, dict):
                episode_num = task.params.get("episode_num", 1)

            await update_task_status(db, task_id, "running", progress=50)

            # Stub: 创建占位脚本数据
            from app.models.project import DramaEpisode
            result = await db.execute(
                select(DramaEpisode).where(
                    DramaEpisode.project_id == str(task.project_id),
                    DramaEpisode.episode_num == episode_num,
                )
            )
            episode = result.scalar_one_or_none()
            if episode:
                episode.outline_json = {
                    "hook": {"first_3s": {"visual": "占位：开局钩子画面", "action": "主角登场"}},
                    "story_beats": [{"beat_num": 1, "type": "setup", "content": "占位剧情"}],
                    "cliffhanger": {"last_5s": {"visual": "占位：悬念画面"}},
                }
                episode.script_json = {
                    "scenes": [
                        {
                            "scene_num": 1,
                            "location": "占位场景",
                            "shots": [
                                {
                                    "shot_num": 1,
                                    "type": "特写",
                                    "duration": "3秒",
                                    "visual": "占位画面描述",
                                    "dialogue": {"speaker": "主角", "content": "占位台词"},
                                }
                            ],
                        }
                    ],
                }
                episode.status = "generated"
                await db.commit()

            await update_task_status(
                db,
                task_id,
                "success",
                progress=100,
                result={"episode_num": episode_num, "script_saved": True},
            )
            logger.info(f"Drama episode task {task_id} completed successfully")
        except Exception as e:
            logger.exception(f"Drama episode task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass