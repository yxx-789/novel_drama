import copy
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import AsyncSessionLocal
from app.models.project import AssetVersion, Project, ProjectAsset, Task
from app.services.drama_service import generate_drama_outline, generate_drama_script
from app.services.generation_service import (
    _structure_for_project,
    build_arc_summary,
    build_state_summary,
    check_chapter_consistency,
    extract_chapter_memory,
    extract_world_state_delta,
    generate_architecture,
    generate_chapter_draft,
    generate_directory,
    load_active_character_cards,
    merge_world_state,
    parse_chapter_blueprint,
    synthesize_book_summary,
    update_character_cards,
)
from app.generator.foreshadowing_ledger import (
    build_foreshadowing_reminder,
    build_known_by_constraints,
    merge_foreshadowing_delta,
)
from app.generator.genre_methodology import get_genre_methodology
from app.generator.world_state_templates import get_template
from app.services.inspiration_service import build_inspiration_guidance
from app.services.llm_config_service import resolve_llm_config
from app.services.project_service import get_project_by_id
from app.core.config import settings

logger = logging.getLogger(__name__)

# V3 P3-B：arc 章节数（可配置化，默认 15，环境变量 ARC_SIZE 覆盖）。arc 边界
# （chapter_num % ARC_SIZE == 0）触发一次 arc 摘要合成（L2），写前追加已冻结 arc 摘要、
# 全书脉络（L3）与伏笔提醒/信息约束，写后台账合并。
# 模块加载时读 settings 一次并保留模块级名字：既有 @patch("task_service.ARC_SIZE", N)
# 测试可原样替换模块属性，无需逐个改 patch 目标。
ARC_SIZE = settings.ARC_SIZE


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


VERSIONED_ASSET_TYPES = ("architecture", "directory")


async def record_asset_version(
    db: AsyncSession,
    project_id: str,
    asset_type: str,
    content_text: str,
    version: int,
    trigger_type: str = "generate",
    guidance: str | None = None,
    created_by: str | None = None,
) -> None:
    """把一次写入记入 asset_versions 历史表（仅 architecture/directory）。"""
    if asset_type not in VERSIONED_ASSET_TYPES:
        return
    db.add(AssetVersion(
        project_id=project_id,
        asset_type=asset_type,
        content_text=content_text,
        version=version,
        trigger_type=trigger_type,
        guidance=guidance,
        created_by=created_by,
    ))
    await db.commit()


async def _save_asset(
    db: AsyncSession,
    project_id: str,
    asset_type: str,
    content_text: str,
    trigger_type: str = "generate",
    guidance: str | None = None,
    created_by: str | None = None,
) -> None:
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
        asset.updated_by = created_by
    else:
        asset = ProjectAsset(
            project_id=project_id,
            asset_type=asset_type,
            content_text=content_text,
            version=1,
            updated_by=created_by,
        )
        db.add(asset)
    await db.commit()
    await db.refresh(asset)
    if asset_type in VERSIONED_ASSET_TYPES:
        await record_asset_version(
            db,
            project_id,
            asset_type,
            content_text,
            version=asset.version,
            trigger_type=trigger_type,
            guidance=guidance,
            created_by=created_by,
        )


async def rollback_asset(
    db: AsyncSession,
    project_id: str,
    asset_type: str,
    version: int,
    user_id: str | None = None,
) -> bool:
    """把指定历史版本写回当前 asset；成功返回 True，目标版本不存在返回 False。"""
    result = await db.execute(
        select(AssetVersion).where(
            AssetVersion.project_id == project_id,
            AssetVersion.asset_type == asset_type,
            AssetVersion.version == version,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        return False

    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_text = target.content_text
        asset.version += 1
        asset.updated_by = user_id
    else:
        asset = ProjectAsset(
            project_id=project_id,
            asset_type=asset_type,
            content_text=target.content_text,
            version=1,
            updated_by=user_id,
        )
        db.add(asset)
    await db.commit()
    await db.refresh(asset)
    await record_asset_version(
        db,
        project_id,
        asset_type,
        target.content_text,
        version=asset.version,
        trigger_type="rollback",
        guidance=f"回滚至 v{version}",
        created_by=user_id,
    )
    return True


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

            # 注入已导入灵感的创作引导
            try:
                guidance = await build_inspiration_guidance(db, str(task.project_id))
                if guidance:
                    user_guidance = f"{user_guidance}\n\n【创作灵感参考】\n{guidance}".strip()
            except Exception as e:
                logger.warning(f"Inspiration guidance injection failed: {e}")

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

            # 注入已导入灵感的创作引导
            try:
                guidance = await build_inspiration_guidance(db, str(task.project_id))
                if guidance:
                    user_guidance = f"{user_guidance}\n\n【创作灵感参考】\n{guidance}".strip()
            except Exception as e:
                logger.warning(f"Inspiration guidance injection failed: {e}")

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


def _previous_chapter_summary(prev_chapter) -> str:
    """
    取前章概要，作为下一章生成的衔接上下文。

    优先级：
    1. prev.actual_summary_json["summary"]（结构化记忆提取的实际摘要）
    2. prev.outline（章节目录规划摘要，旧项目无 actual_summary_json 时的回退）
    3. ""（无前章）

    任何一步缺失或为空都会平滑回退，保证旧数据/旧管线行为不变。
    """
    if prev_chapter is None:
        return ""
    memory = getattr(prev_chapter, "actual_summary_json", None)
    if isinstance(memory, dict) and isinstance(memory.get("summary"), str) and memory["summary"].strip():
        return memory["summary"]
    return prev_chapter.outline or ""


# =================== V3 P3-B 记忆分层接线辅助 ===================

async def _get_asset_json(db: AsyncSession, project_id: str, asset_type: str) -> dict | None:
    """读取 JSON 资产（content_json）；无资产 / 非 dict → None。"""
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset or not isinstance(asset.content_json, dict):
        return None
    return asset.content_json


async def _save_asset_json(db: AsyncSession, project_id: str, asset_type: str, content: dict) -> None:
    """写入 JSON 资产（content_json）；不存在则新建。"""
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_json = content
        asset.version += 1
    else:
        asset = ProjectAsset(
            project_id=project_id,
            asset_type=asset_type,
            content_json=content,
        )
        db.add(asset)
    await db.commit()


async def _build_l2_foreshadowing_context(
    db: AsyncSession, project_id: str, chapter_num: int, genre: str
) -> str:
    """写前组装 L2 上下文：已冻结 arc 摘要（最近完成 arc）+ 全书脉络（L3）+ 伏笔/副线提醒 + known_by 信息约束。

    纯资产读取 + 纯规则，零新增 LLM 调用；无内容返回空串。
    """
    parts = []

    # 已冻结 arc 摘要（最近完成 arc；arc 在边界冻结，之后的章开始注入）
    arc_data = await _get_asset_json(db, project_id, "arc_summaries")
    arcs = arc_data.get("arcs") if isinstance(arc_data, dict) else None
    if isinstance(arcs, list) and arcs:
        last_arc = arcs[-1]
        if isinstance(last_arc, dict):
            summary = last_arc.get("summary")
            if isinstance(summary, str) and summary.strip():
                parts.append(f"【已冻结 arc 摘要】{summary.strip()}")

    # 伏笔/副线提醒 + known_by 信息约束（methodology 与 merge_foreshadowing_delta 内取同源题材参数）
    ledger = await _get_asset_json(db, project_id, "foreshadowing")
    if isinstance(ledger, dict):
        methodology = get_genre_methodology(genre)
        reminder = build_foreshadowing_reminder(
            ledger, current_chapter=chapter_num, methodology=methodology
        )
        # L3 全书脉络：仅当有伏笔提醒（需回溯早期细节）时注入，避免常驻 token
        if reminder:
            bs = arc_data.get("book_summary") if isinstance(arc_data, dict) else None
            if isinstance(bs, dict):
                book_summary = bs.get("summary")
                if isinstance(book_summary, str) and book_summary.strip():
                    parts.append(f"【全书脉络】{book_summary.strip()}")
            parts.append(f"【伏笔/副线提醒】{reminder}")
        # known_by 信息约束：每章注入（最近触碰 + 提醒命中），防角色说出不该知道的事
        constraints = build_known_by_constraints(
            ledger, current_chapter=chapter_num, methodology=methodology
        )
        if constraints:
            parts.append(f"【信息约束】\n{constraints}")

    return "\n\n".join(parts)


async def _merge_foreshadowing_ledger(
    db: AsyncSession, project_id: str, chapter_num: int, memory: dict, genre: str
) -> None:
    """写后台账合并：把本章记忆的伏笔/副线字段并入 foreshadowing 资产。失败不中断。

    无变化（merge 前后深比较相等）时跳过写回，避免空跳 version；但资产缺失时
    仍初始化写入空台账（旧项目兼容：首章也建立台账结构）。
    """
    try:
        ledger = await _get_asset_json(db, project_id, "foreshadowing")
        existed = isinstance(ledger, dict)
        if not existed:
            ledger = {"entries": [], "unmatched": []}
        before = copy.deepcopy(ledger)  # merge_foreshadowing_delta 原地修改，必须快照比较
        merged = merge_foreshadowing_delta(ledger, memory, genre, chapter_num)
        if not existed or merged != before:
            await _save_asset_json(db, project_id, "foreshadowing", merged)
    except Exception as e:
        logger.warning(f"Foreshadowing ledger merge failed for chapter {chapter_num}: {e}")


async def _finalize_arc_summary(
    db: AsyncSession, project_id: str, chapter_num: int, llm_config: dict
) -> None:
    """arc 边界（chapter_num % ARC_SIZE == 0）冻结 arc 摘要（L2），冻结不覆盖。失败不中断。"""
    if chapter_num % ARC_SIZE != 0:
        return
    try:
        from app.models.project import Chapter
        arc_start = chapter_num - ARC_SIZE + 1
        arc_index = chapter_num // ARC_SIZE - 1
        # 冻结不覆盖：同 arc_index 已存在则跳过（先查资产，避免重复触发 arc 摘要 LLM 调用）
        arc_data = await _get_asset_json(db, project_id, "arc_summaries")
        if not isinstance(arc_data, dict):
            arc_data = {"arcs": [], "book_summary": {}}
        arcs = arc_data.get("arcs")
        if not isinstance(arcs, list):
            arcs = []
            arc_data["arcs"] = arcs
        if any(isinstance(a, dict) and a.get("arc_index") == arc_index for a in arcs):
            return
        result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_num >= arc_start,
                Chapter.chapter_num <= chapter_num,
            ).order_by(Chapter.chapter_num)
        )
        chapters = list(result.scalars().all())
        if not chapters:
            return
        arc = await build_arc_summary(chapters, llm_config, arc_size=ARC_SIZE)
        if not arc:
            return
        arcs.append({
            "arc_index": arc_index,
            "chapter_range": arc.get("chapter_range") or [arc_start, chapter_num],
            "title": f"第{arc_start}-{chapter_num}章",
            "summary": arc.get("summary", ""),
            "frozen_at": datetime.now(timezone.utc).isoformat(),
        })
        await _save_asset_json(db, project_id, "arc_summaries", arc_data)
        logger.info(f"Arc {arc_index} summary frozen for chapters {arc_start}-{chapter_num}")
    except Exception as e:
        logger.warning(f"Arc summary finalize failed for chapter {chapter_num}: {e}")


async def _synthesize_book_summary_asset(
    db: AsyncSession, project_id: str, llm_config: dict
) -> None:
    """全书写完（batch 循环结束）时合成全书摘要（L3）。无已冻结 arc 时跳过。失败不中断。"""
    try:
        arc_data = await _get_asset_json(db, project_id, "arc_summaries")
        arcs = arc_data.get("arcs") if isinstance(arc_data, dict) else None
        if not isinstance(arcs, list) or not arcs:
            return
        summary = await synthesize_book_summary(arcs, llm_config)
        if not summary:
            return
        arc_data["book_summary"] = {
            "summary": summary,
            "synthesized_at": datetime.now(timezone.utc).isoformat(),
        }
        await _save_asset_json(db, project_id, "arc_summaries", arc_data)
        logger.info("Book summary synthesized")
    except Exception as e:
        logger.warning(f"Book summary synthesis failed: {e}")


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
            structure = _structure_for_project(project)

            chapter_num = 1
            if task.params and isinstance(task.params, dict):
                chapter_num = task.params.get("chapter_num", 1)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            directory_text = await _get_asset_text(db, str(task.project_id), "directory")
            if not directory_text:
                raise RuntimeError("Directory not found. Please generate directory first.")

            # P2-B: 写前只加载出场角色卡（结构化卡项目只注入出场角色，旧文本项目原样返回）
            character_state_text = await load_active_character_cards(db, str(task.project_id), chapter_num) or ""

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
                    previous_summary = _previous_chapter_summary(prev_chapter)

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
                        structure=structure,
                    )
                except Exception as e:
                    logger.warning(f"Build state summary failed for chapter {chapter_num}: {e}")

            # V3 P3-B：写前追加 L2 上下文（已冻结 arc 摘要 + 伏笔/副线提醒），零新增 LLM 调用
            try:
                l2_context = await _build_l2_foreshadowing_context(
                    db, str(task.project_id), chapter_num, project.genre or ""
                )
                if l2_context:
                    world_state_summary = (
                        f"{world_state_summary}\n\n{l2_context}".strip()
                        if world_state_summary else l2_context
                    )
            except Exception as e:
                logger.warning(f"L2 context build failed for chapter {chapter_num}: {e}")

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

            # P2-B: 更新角色卡（结构化档案双通道写回；失败不中断生成，保留旧状态）
            try:
                await update_character_cards(
                    db, str(task.project_id), chapter_num, draft_text, llm_config=llm_config,
                )
            except Exception as e:
                logger.warning(f"Character cards update failed for chapter {chapter_num}: {e}")

            # 提取并更新 world_state（非阻塞）
            try:
                delta = await extract_world_state_delta(
                    chapter_text=draft_text,
                    chapter_number=chapter_num,
                    current_state=world_state,
                    template=template,
                    llm_config=llm_config,
                    structure=structure,
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

            # 结构化章节记忆提取（非阻塞，失败不中断生成）
            memory = {}
            try:
                memory = await extract_chapter_memory(db, chapter, llm_config)
                if memory and memory.get("summary"):
                    chapter.actual_summary_json = memory
                    logger.info(f"Chapter memory extracted for chapter {chapter_num}")
            except Exception as e:
                logger.warning(f"Chapter memory extraction failed for chapter {chapter_num}: {e}")

            await db.commit()

            # V3 P3-B：写后台账合并（纯规则）+ arc 边界冻结（失败不中断）
            if memory and memory.get("summary"):
                await _merge_foreshadowing_ledger(
                    db, str(task.project_id), chapter_num, memory, project.genre or ""
                )
            await _finalize_arc_summary(db, str(task.project_id), chapter_num, llm_config)

            # V3 P3-B 闭环：单章路径写到全书最后一章时合成一次全书摘要（L3，摊薄 1/N），
            # 与批量路径（循环结束合成）行为对称；num_chapters 未设（0/None）时跳过。
            total_chapters = getattr(project, "num_chapters", 0) or 0
            if total_chapters and chapter_num == total_chapters:
                try:
                    await _synthesize_book_summary_asset(
                        db, str(task.project_id), llm_config
                    )
                except Exception as e:
                    logger.warning(f"Book summary synthesis failed for task {task_id}: {e}")

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
            structure = _structure_for_project(project)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            directory_text = await _get_asset_text(db, str(task.project_id), "directory")
            if not directory_text:
                raise RuntimeError("Directory not found. Please generate directory first.")

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
                            previous_summary = _previous_chapter_summary(prev_chapter)

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
                                structure=structure,
                            )
                        except Exception as e:
                            logger.warning(f"Batch build state summary failed for chapter {chapter_num}: {e}")

                    # V3 P3-B：写前追加 L2 上下文（已冻结 arc 摘要 + 伏笔/副线提醒），零新增 LLM 调用
                    try:
                        l2_context = await _build_l2_foreshadowing_context(
                            db, str(task.project_id), chapter_num, project.genre or ""
                        )
                        if l2_context:
                            world_state_summary = (
                                f"{world_state_summary}\n\n{l2_context}".strip()
                                if world_state_summary else l2_context
                            )
                    except Exception as e:
                        logger.warning(f"Batch L2 context build failed for chapter {chapter_num}: {e}")

                    # P2-B: 写前只加载出场角色卡（按本章，不再循环外全量加载一次）
                    character_state_text = await load_active_character_cards(db, str(task.project_id), chapter_num) or ""

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

                    # P2-B: 更新角色卡（结构化档案双通道写回；失败不中断生成，保留旧状态）
                    # 不再内存累积全量状态——下一章从资产重新加载"出场角色卡"
                    try:
                        await update_character_cards(
                            db, str(task.project_id), chapter_num, draft_text, llm_config=llm_config,
                        )
                    except Exception as e:
                        logger.warning(f"Character cards update failed for chapter {chapter_num}: {e}")

                    # 提取并更新 world_state（非阻塞）
                    try:
                        delta = await extract_world_state_delta(
                            chapter_text=draft_text,
                            chapter_number=chapter_num,
                            current_state=world_state,
                            template=template,
                            llm_config=llm_config,
                            structure=structure,
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

                    # 结构化章节记忆提取（非阻塞，失败不中断生成）
                    memory = {}
                    try:
                        memory = await extract_chapter_memory(db, chapter, llm_config)
                        if memory and memory.get("summary"):
                            chapter.actual_summary_json = memory
                            logger.info(f"Batch chapter memory extracted for chapter {chapter_num}")
                    except Exception as e:
                        logger.warning(f"Batch chapter memory extraction failed for chapter {chapter_num}: {e}")

                    await db.commit()

                    # V3 P3-B：写后台账合并（纯规则）+ arc 边界冻结（失败不中断）
                    if memory and memory.get("summary"):
                        await _merge_foreshadowing_ledger(
                            db, str(task.project_id), chapter_num, memory, project.genre or ""
                        )
                    await _finalize_arc_summary(db, str(task.project_id), chapter_num, llm_config)

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

            # V3 P3-B：全书写完（循环结束）合成全书摘要（L3）；失败不中断
            try:
                await _synthesize_book_summary_asset(db, str(task.project_id), llm_config)
            except Exception as e:
                logger.warning(f"Book summary synthesis failed for task {task_id}: {e}")

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