import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import AsyncSessionLocal
from app.models.project import Project, ProjectAsset, Task
from app.services.drama_service import generate_drama_outline, generate_drama_script
from app.services.generation_service import (
    build_state_summary,
    check_chapter_consistency,
    extract_world_state_delta,
    generate_architecture,
    generate_chapter_draft,
    generate_directory,
    merge_world_state,
    parse_chapter_blueprint,
    update_character_state,
)
from app.generator.world_state_templates import get_template
from app.services.llm_config_service import resolve_llm_config
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

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            user_guidance = ""
            if task.params and isinstance(task.params, dict):
                user_guidance = task.params.get("user_guidance", "")

            await update_task_status(db, task_id, "running", progress=30)
            architecture_text, character_state_text = await generate_architecture(
                project, user_guidance=user_guidance, llm_config=llm_config
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
    """根据解析的目录，初始化或更新 chapters 表记录"""
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
        else:
            # 更新已有记录的标题和摘要
            if ch["chapter_title"]:
                existing.title = ch["chapter_title"]
            if ch["chapter_summary"]:
                existing.outline = ch["chapter_summary"]
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

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            user_guidance = ""
            if task.params and isinstance(task.params, dict):
                user_guidance = task.params.get("user_guidance", "")

            await update_task_status(db, task_id, "running", progress=40)
            directory_text, parsed_chapters = await generate_directory(
                project, architecture_text=architecture_text, user_guidance=user_guidance, llm_config=llm_config
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

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            chapter_num = 1
            if task.params and isinstance(task.params, dict):
                chapter_num = task.params.get("chapter_num", 1)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            directory_text = await _get_asset_text(db, str(task.project_id), "directory")
            if not directory_text:
                raise RuntimeError("Directory not found. Please generate directory first.")

            character_state_text = await _get_asset_text(db, str(task.project_id), "characters") or ""

            # 读取 world_state
            world_state_raw = await _get_asset_text(db, str(task.project_id), "world_state")
            world_state: dict = {}
            if world_state_raw:
                try:
                    world_state = json.loads(world_state_raw)
                except Exception:
                    world_state = {}
            template = get_template(project.genre or "")

            await update_task_status(db, task_id, "running", progress=30)

            previous_draft = None
            previous_summary = ""
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
                    previous_summary = prev_chapter.outline or ""

            # 构建 world_state 摘要
            world_state_summary = ""
            if world_state:
                try:
                    current_chapter_info = None
                    parsed = parse_chapter_blueprint(directory_text)
                    for ch in parsed:
                        if ch["chapter_number"] == chapter_num:
                            current_chapter_info = ch
                            break
                    world_state_summary = await build_state_summary(
                        world_state=world_state,
                        target_chapter=chapter_num,
                        chapter_title=current_chapter_info["chapter_title"] if current_chapter_info else "",
                        chapter_summary=current_chapter_info["chapter_summary"] if current_chapter_info else "",
                        llm_config=llm_config,
                    )
                except Exception as e:
                    logger.warning(f"Build state summary failed for chapter {chapter_num}: {e}")

            await update_task_status(db, task_id, "running", progress=50)
            draft_text = await generate_chapter_draft(
                project,
                chapter_num=chapter_num,
                architecture_text=architecture_text,
                directory_text=directory_text,
                character_state_text=character_state_text,
                previous_chapter_draft=previous_draft,
                previous_chapter_summary=previous_summary,
                world_state_summary=world_state_summary,
                llm_config=llm_config,
            )

            await update_task_status(db, task_id, "running", progress=65)

            # 章节生成后一致性检查（非阻塞）
            if character_state_text:
                try:
                    check_result = await check_chapter_consistency(
                        chapter_text=draft_text,
                        character_state_text=character_state_text,
                        previous_chapter_draft=previous_draft,
                        llm_config=llm_config,
                    )
                    if "INCONSISTENT" in check_result.upper():
                        logger.warning(f"Chapter {chapter_num} consistency issues detected:\n{check_result}")
                    else:
                        logger.info(f"Chapter {chapter_num} consistency check passed.")
                except Exception as e:
                    logger.warning(f"Chapter consistency check failed for chapter {chapter_num}: {e}")

            await update_task_status(db, task_id, "running", progress=70)

            # 更新角色状态
            if character_state_text:
                try:
                    new_state = await update_character_state(
                        chapter_text=draft_text,
                        old_state=character_state_text,
                        llm_config=llm_config,
                    )
                    await _save_asset(db, str(task.project_id), "characters", new_state)
                except Exception as e:
                    logger.warning(f"Character state update failed for chapter {chapter_num}: {e}")

            # 提取并更新 world_state（非阻塞）
            try:
                delta = await extract_world_state_delta(
                    chapter_text=draft_text,
                    chapter_number=chapter_num,
                    current_state=world_state,
                    template=template,
                    llm_config=llm_config,
                )
                if not delta.get("no_changes"):
                    world_state = merge_world_state(world_state, delta)
                    await _save_asset(
                        db, str(task.project_id), "world_state",
                        json.dumps(world_state, ensure_ascii=False, indent=2)
                    )
                    logger.info(f"World state updated for chapter {chapter_num}")
            except Exception as e:
                logger.warning(f"World state update failed for chapter {chapter_num}: {e}")

            await update_task_status(db, task_id, "running", progress=85)

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


async def run_batch_chapters_task(task_id: uuid.UUID) -> None:
    """后台执行批量章节正文生成任务（串行逐章生成）"""
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=5)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            directory_text = await _get_asset_text(db, str(task.project_id), "directory")
            if not directory_text:
                raise RuntimeError("Directory not found. Please generate directory first.")

            character_state_text = await _get_asset_text(db, str(task.project_id), "characters") or ""

            # 读取 world_state
            world_state_raw = await _get_asset_text(db, str(task.project_id), "world_state")
            world_state: dict = {}
            if world_state_raw:
                try:
                    world_state = json.loads(world_state_raw)
                except Exception:
                    world_state = {}
            template = get_template(project.genre or "")

            # 获取所有需要生成的章节
            from app.models.project import Chapter
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                ).order_by(Chapter.chapter_num)
            )
            chapter_list = list(result.scalars().all())
            total = len(chapter_list)
            if total == 0:
                raise RuntimeError("No chapters found. Please generate directory first.")

            await update_task_status(db, task_id, "running", progress=10)

            generated_count = 0
            failed_chapters = []
            for idx, chapter in enumerate(chapter_list):
                chapter_num = chapter.chapter_num
                logger.info(f"Batch task {task_id}: generating chapter {chapter_num} ({idx + 1}/{total}) ...")

                try:
                    previous_draft = None
                    previous_summary = ""
                    if chapter_num > 1:
                        result = await db.execute(
                            select(Chapter).where(
                                Chapter.project_id == str(task.project_id),
                                Chapter.chapter_num == chapter_num - 1,
                            )
                        )
                        prev_chapter = result.scalar_one_or_none()
                        if prev_chapter:
                            previous_draft = prev_chapter.draft
                            previous_summary = prev_chapter.outline or ""

                    # 构建 world_state 摘要
                    world_state_summary = ""
                    if world_state:
                        try:
                            parsed = parse_chapter_blueprint(directory_text)
                            current_chapter_info = None
                            for ch in parsed:
                                if ch["chapter_number"] == chapter_num:
                                    current_chapter_info = ch
                                    break
                            world_state_summary = await build_state_summary(
                                world_state=world_state,
                                target_chapter=chapter_num,
                                chapter_title=current_chapter_info["chapter_title"] if current_chapter_info else "",
                                chapter_summary=current_chapter_info["chapter_summary"] if current_chapter_info else "",
                                llm_config=llm_config,
                            )
                        except Exception as e:
                            logger.warning(f"Batch build state summary failed for chapter {chapter_num}: {e}")

                    draft_text = await generate_chapter_draft(
                        project,
                        chapter_num=chapter_num,
                        architecture_text=architecture_text,
                        directory_text=directory_text,
                        character_state_text=character_state_text,
                        previous_chapter_draft=previous_draft,
                        previous_chapter_summary=previous_summary,
                        world_state_summary=world_state_summary,
                        llm_config=llm_config,
                    )

                    chapter.draft = draft_text
                    chapter.status = "draft_generated"

                    # 章节生成后一致性检查（非阻塞）
                    if character_state_text:
                        try:
                            check_result = await check_chapter_consistency(
                                chapter_text=draft_text,
                                character_state_text=character_state_text,
                                previous_chapter_draft=previous_draft,
                                llm_config=llm_config,
                            )
                            if "INCONSISTENT" in check_result.upper():
                                logger.warning(f"Batch chapter {chapter_num} consistency issues detected:\n{check_result}")
                            else:
                                logger.info(f"Batch chapter {chapter_num} consistency check passed.")
                        except Exception as e:
                            logger.warning(f"Batch chapter consistency check failed for chapter {chapter_num}: {e}")

                    # 更新角色状态
                    if character_state_text:
                        try:
                            new_state = await update_character_state(
                                chapter_text=draft_text,
                                old_state=character_state_text,
                                llm_config=llm_config,
                            )
                            character_state_text = new_state
                            await _save_asset(db, str(task.project_id), "characters", new_state)
                        except Exception as e:
                            logger.warning(f"Character state update failed for chapter {chapter_num}: {e}")

                    # 提取并更新 world_state（非阻塞）
                    try:
                        delta = await extract_world_state_delta(
                            chapter_text=draft_text,
                            chapter_number=chapter_num,
                            current_state=world_state,
                            template=template,
                            llm_config=llm_config,
                        )
                        if not delta.get("no_changes"):
                            world_state = merge_world_state(world_state, delta)
                            await _save_asset(
                                db, str(task.project_id), "world_state",
                                json.dumps(world_state, ensure_ascii=False, indent=2)
                            )
                            logger.info(f"Batch world state updated for chapter {chapter_num}")
                    except Exception as e:
                        logger.warning(f"Batch world state update failed for chapter {chapter_num}: {e}")

                    await db.commit()
                    generated_count += 1
                except Exception as e:
                    logger.exception(f"Batch chapter {chapter_num} generation failed: {e}")
                    failed_chapters.append({"chapter_num": chapter_num, "error": str(e)})
                    await db.commit()

                progress = 10 + int((idx + 1) / total * 85)
                await update_task_status(
                    db, task_id, "running", progress=progress,
                    result={
                        "current_chapter": chapter_num,
                        "completed": generated_count,
                        "total": total,
                        "failed": len(failed_chapters),
                        "failed_chapters": failed_chapters,
                    }
                )

            if failed_chapters:
                await update_task_status(
                    db, task_id, "success", progress=100,
                    result={
                        "total": total,
                        "generated": generated_count,
                        "failed_count": len(failed_chapters),
                        "failed_chapters": failed_chapters,
                    }
                )
                logger.warning(f"Batch chapters task {task_id} completed with failures: {generated_count}/{total}, failed: {failed_chapters}")
            else:
                await update_task_status(
                    db, task_id, "success", progress=100,
                    result={"total": total, "generated": generated_count}
                )
                logger.info(f"Batch chapters task {task_id} completed: {generated_count}/{total}")
        except Exception as e:
            logger.exception(f"Batch chapters task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass


async def run_drama_plan_task(task_id: uuid.UUID) -> None:
    """后台执行短剧改编计划生成任务"""
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

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            # 读取章节正文和角色设定
            from app.models.project import Chapter
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                ).order_by(Chapter.chapter_num)
            )
            chapters = list(result.scalars().all())
            if not chapters:
                raise RuntimeError("No chapters found. Please generate chapters first.")

            characters_text = await _get_asset_text(db, str(task.project_id), "characters") or ""

            await update_task_status(db, task_id, "running", progress=25)

            # 按每 3 章一集分组并生成真实大纲
            chapters_per_episode = 3
            episodes = []
            total = len(chapters)
            for i in range(0, total, chapters_per_episode):
                batch = chapters[i:i + chapters_per_episode]
                start_num = batch[0].chapter_num
                end_num = batch[-1].chapter_num
                episode_num = i // chapters_per_episode + 1
                chapters_range = f"第{start_num}-{end_num}章" if start_num != end_num else f"第{start_num}章"

                # 合并章节文本
                chapter_texts = "\n\n".join(
                    f"=== 第{ch.chapter_num}章 ===\n{ch.draft or ''}" for ch in batch
                )

                await update_task_status(
                    db, task_id, "running",
                    progress=25 + int((i / total) * 60),
                    result={"current_episode": episode_num, "total_episodes": (total + 2) // 3}
                )

                outline = await generate_drama_outline(
                    chapter_texts=chapter_texts,
                    characters_text=characters_text,
                    episode_num=episode_num,
                    chapters_range=chapters_range,
                    llm_config=llm_config,
                )

                episodes.append({
                    "episode_num": episode_num,
                    "title": outline.get("title", f"第{episode_num}集"),
                    "source_chapters": chapters_range,
                    "outline_json": outline,
                })

            await update_task_status(db, task_id, "running", progress=90)
            await _ensure_drama_episodes(db, str(task.project_id), episodes)

            # 保存 outline_json
            from app.models.project import DramaEpisode
            for ep in episodes:
                result = await db.execute(
                    select(DramaEpisode).where(
                        DramaEpisode.project_id == str(task.project_id),
                        DramaEpisode.episode_num == ep["episode_num"],
                    )
                )
                episode = result.scalar_one_or_none()
                if episode:
                    episode.outline_json = ep["outline_json"]
                    episode.title = ep["title"]
                    episode.source_chapters = ep["source_chapters"]
                    episode.status = "outlined"
            await db.commit()

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
    """后台执行单集短剧脚本生成任务"""
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

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            episode_num = 1
            if task.params and isinstance(task.params, dict):
                episode_num = task.params.get("episode_num", 1)

            from app.models.project import DramaEpisode
            result = await db.execute(
                select(DramaEpisode).where(
                    DramaEpisode.project_id == str(task.project_id),
                    DramaEpisode.episode_num == episode_num,
                )
            )
            episode = result.scalar_one_or_none()
            if not episode:
                raise RuntimeError(f"Episode {episode_num} not found")

            if not episode.outline_json:
                raise RuntimeError(f"Episode {episode_num} has no outline. Please run drama plan first.")

            # 读取对应范围的章节文本
            from app.models.project import Chapter
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                ).order_by(Chapter.chapter_num)
            )
            chapters = list(result.scalars().all())

            # 优先使用用户指定的 chapter_nums，否则按 source_chapters 自动匹配
            chapter_nums = None
            if task.params and isinstance(task.params, dict):
                chapter_nums = task.params.get("chapter_nums")

            chapter_texts = ""
            if chapter_nums:
                selected = [ch for ch in chapters if ch.chapter_num in chapter_nums]
                selected.sort(key=lambda c: c.chapter_num)
                chapter_texts = "\n\n".join(
                    f"=== 第{ch.chapter_num}章 ===\n{ch.draft or ''}" for ch in selected
                )
            else:
                # 解析 source_chapters 范围，例如 "第1-3章"
                source = episode.source_chapters or ""
                if source:
                    import re
                    range_match = re.search(r"第(\d+)-(\d+)章", source)
                    if range_match:
                        start, end = int(range_match.group(1)), int(range_match.group(2))
                        selected = [ch for ch in chapters if start <= ch.chapter_num <= end]
                    else:
                        single_match = re.search(r"第(\d+)章", source)
                        if single_match:
                            num = int(single_match.group(1))
                            selected = [ch for ch in chapters if ch.chapter_num == num]
                        else:
                            selected = chapters
                    chapter_texts = "\n\n".join(
                        f"=== 第{ch.chapter_num}章 ===\n{ch.draft or ''}" for ch in selected
                    )
                else:
                    chapter_texts = "\n\n".join(
                        f"=== 第{ch.chapter_num}章 ===\n{ch.draft or ''}" for ch in chapters
                    )

            characters_text = await _get_asset_text(db, str(task.project_id), "characters") or ""

            # 记忆机制：查询前 N-1 集已生成的脚本作为上下文
            context_scripts = []
            if episode_num > 1:
                prev_result = await db.execute(
                    select(DramaEpisode).where(
                        DramaEpisode.project_id == str(task.project_id),
                        DramaEpisode.episode_num < episode_num,
                        DramaEpisode.script_json.isnot(None),
                    ).order_by(DramaEpisode.episode_num)
                )
                for prev_ep in prev_result.scalars().all():
                    context_scripts.append(prev_ep.script_json)

            await update_task_status(db, task_id, "running", progress=40)

            script = await generate_drama_script(
                outline=episode.outline_json,
                chapter_texts=chapter_texts,
                characters_text=characters_text,
                context_scripts=context_scripts,
                llm_config=llm_config,
            )

            await update_task_status(db, task_id, "running", progress=80)

            episode.script_json = script
            episode.status = "script_ready"
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


async def run_drama_batch_task(task_id: uuid.UUID) -> None:
    """后台执行批量短剧脚本生成任务（串行逐集生成）"""
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=5)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            llm_config = await resolve_llm_config(str(project.owner_id), db)

            from app.models.project import DramaEpisode, Chapter
            result = await db.execute(
                select(DramaEpisode).where(
                    DramaEpisode.project_id == str(task.project_id),
                ).order_by(DramaEpisode.episode_num)
            )
            episodes = list(result.scalars().all())
            total = len(episodes)
            if total == 0:
                raise RuntimeError("No drama episodes found. Please run drama plan first.")

            # 预加载全部章节
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                ).order_by(Chapter.chapter_num)
            )
            chapters = list(result.scalars().all())
            characters_text = await _get_asset_text(db, str(task.project_id), "characters") or ""

            await update_task_status(db, task_id, "running", progress=10)

            generated_count = 0
            for idx, episode in enumerate(episodes):
                episode_num = episode.episode_num
                logger.info(f"Drama batch task {task_id}: generating episode {episode_num} ({idx + 1}/{total}) ...")

                if not episode.outline_json:
                    logger.warning(f"Episode {episode_num} has no outline, skipping")
                    continue

                # 解析 source_chapters 范围
                source = episode.source_chapters or ""
                chapter_texts = ""
                if source:
                    import re
                    range_match = re.search(r"第(\d+)-(\d+)章", source)
                    if range_match:
                        start, end = int(range_match.group(1)), int(range_match.group(2))
                        selected = [ch for ch in chapters if start <= ch.chapter_num <= end]
                    else:
                        single_match = re.search(r"第(\d+)章", source)
                        if single_match:
                            num = int(single_match.group(1))
                            selected = [ch for ch in chapters if ch.chapter_num == num]
                        else:
                            selected = chapters
                    chapter_texts = "\n\n".join(
                        f"=== 第{ch.chapter_num}章 ===\n{ch.draft or ''}" for ch in selected
                    )
                else:
                    chapter_texts = "\n\n".join(
                        f"=== 第{ch.chapter_num}章 ===\n{ch.draft or ''}" for ch in chapters
                    )

                # 记忆机制：查询前 N-1 集已生成的脚本作为上下文
                context_scripts = []
                if episode.episode_num > 1:
                    prev_result = await db.execute(
                        select(DramaEpisode).where(
                            DramaEpisode.project_id == str(task.project_id),
                            DramaEpisode.episode_num < episode.episode_num,
                            DramaEpisode.script_json.isnot(None),
                        ).order_by(DramaEpisode.episode_num)
                    )
                    for prev_ep in prev_result.scalars().all():
                        context_scripts.append(prev_ep.script_json)

                script = await generate_drama_script(
                    outline=episode.outline_json,
                    chapter_texts=chapter_texts,
                    characters_text=characters_text,
                    context_scripts=context_scripts,
                    llm_config=llm_config,
                )

                episode.script_json = script
                episode.status = "script_ready"
                await db.commit()

                generated_count += 1
                progress = 10 + int((generated_count / total) * 85)
                await update_task_status(
                    db, task_id, "running", progress=progress,
                    result={"current_episode": episode_num, "completed": generated_count, "total": total}
                )

            await update_task_status(
                db, task_id, "success", progress=100,
                result={"total": total, "generated": generated_count}
            )
            logger.info(f"Drama batch task {task_id} completed: {generated_count}/{total}")
        except Exception as e:
            logger.exception(f"Drama batch task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass