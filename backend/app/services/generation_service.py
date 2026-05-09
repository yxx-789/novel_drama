# generation_service.py
# -*- coding: utf-8 -*-
"""
小说生成服务：复用 AI_NovelGenerator 核心逻辑，改造为异步 + 数据库驱动
"""

import logging
import uuid

from app.core.config import settings
from app.generator.llm_adapter import create_llm_adapter
import re

from app.generator.prompts import (
    architecture_consistency_prompt,
    chapter_blueprint_prompt,
    character_dynamics_prompt,
    core_seed_prompt,
    create_character_state_prompt,
    first_chapter_draft_prompt,
    next_chapter_draft_prompt,
    plot_architecture_prompt,
    update_character_state_prompt,
    world_building_prompt,
)
from app.models.project import Project

logger = logging.getLogger(__name__)


async def _invoke_with_retry(adapter, prompt: str, max_retries: int = 3) -> str:
    """调用 LLM，带重试和输出清洗"""
    for attempt in range(max_retries):
        try:
            result = await adapter.invoke(prompt)
            cleaned = result.replace("```", "").strip()
            if cleaned:
                return cleaned
            logger.warning(f"Empty response on attempt {attempt + 1}")
        except Exception as e:
            logger.warning(f"LLM invoke failed on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise
    return ""


async def generate_architecture(
    project: Project,
    user_guidance: str = "",
) -> tuple[str, str]:
    """
    5 步架构生成 pipeline。
    返回：(architecture_text, character_state_text)
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API key not configured")

    adapter = create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )

    topic = project.topic or ""
    genre = project.genre or ""
    number_of_chapters = project.num_chapters or 10
    word_number = project.word_number or 2000

    # Step1: 核心种子
    logger.info("Step1: Generating core_seed_prompt ...")
    prompt_core = core_seed_prompt.format(
        topic=topic,
        genre=genre,
        number_of_chapters=number_of_chapters,
        word_number=word_number,
        user_guidance=user_guidance,
    )
    core_seed_result = await _invoke_with_retry(adapter, prompt_core)
    if not core_seed_result:
        raise RuntimeError("core_seed_prompt generation failed")

    # Step2: 角色动力学
    logger.info("Step2: Generating character_dynamics_prompt ...")
    prompt_character = character_dynamics_prompt.format(
        core_seed=core_seed_result,
        user_guidance=user_guidance,
    )
    character_dynamics_result = await _invoke_with_retry(adapter, prompt_character)
    if not character_dynamics_result:
        raise RuntimeError("character_dynamics_prompt generation failed")

    # Step3: 角色状态初始化
    logger.info("Step3: Generating character_state ...")
    prompt_char_state = create_character_state_prompt.format(
        character_dynamics=character_dynamics_result,
    )
    character_state_result = await _invoke_with_retry(adapter, prompt_char_state)
    if not character_state_result:
        raise RuntimeError("create_character_state_prompt generation failed")

    # Step4: 世界观
    logger.info("Step4: Generating world_building_prompt ...")
    prompt_world = world_building_prompt.format(
        core_seed=core_seed_result,
        user_guidance=user_guidance,
    )
    world_building_result = await _invoke_with_retry(adapter, prompt_world)
    if not world_building_result:
        raise RuntimeError("world_building_prompt generation failed")

    # Step5: 三幕式情节
    logger.info("Step5: Generating plot_architecture_prompt ...")
    prompt_plot = plot_architecture_prompt.format(
        core_seed=core_seed_result,
        character_dynamics=character_dynamics_result,
        world_building=world_building_result,
        user_guidance=user_guidance,
    )
    plot_arch_result = await _invoke_with_retry(adapter, prompt_plot)
    if not plot_arch_result:
        raise RuntimeError("plot_architecture_prompt generation failed")

    # Step6: 架构一致性校验
    logger.info("Step6: Running architecture consistency check ...")
    try:
        prompt_check = architecture_consistency_prompt.format(
            core_seed=core_seed_result,
            character_dynamics=character_dynamics_result,
            character_state=character_state_result,
            world_building=world_building_result,
            plot_architecture=plot_arch_result,
        )
        check_result = await _invoke_with_retry(adapter, prompt_check)
        if check_result and "INCONSISTENT" in check_result.upper():
            logger.warning(f"Architecture consistency issues detected:\n{check_result}")
        else:
            logger.info("Architecture consistency check passed.")
    except Exception as e:
        logger.warning(f"Architecture consistency check failed (non-blocking): {e}")

    # 组装最终架构文本
    architecture_text = (
        "#=== 0) 小说设定 ===\n"
        f"主题：{topic},类型：{genre},篇幅：约{number_of_chapters}章（每章{word_number}字）\n\n"
        "#=== 1) 核心种子 ===\n"
        f"{core_seed_result}\n\n"
        "#=== 2) 角色动力学 ===\n"
        f"{character_dynamics_result}\n\n"
        "#=== 3) 世界观 ===\n"
        f"{world_building_result}\n\n"
        "#=== 4) 三幕式情节架构 ===\n"
        f"{plot_arch_result}\n"
    )

    logger.info("Architecture generation completed successfully.")
    return architecture_text, character_state_result


def parse_chapter_blueprint(blueprint_text: str) -> list[dict]:
    """复用自 AI_NovelGenerator/chapter_directory_parser.py"""
    # 预处理：去掉 markdown 加粗标记 ** 和行首空白
    cleaned_text = re.sub(r'\*\*', '', blueprint_text)
    chunks = re.split(r'\n\s*\n', cleaned_text.strip())
    results = []
    chapter_number_pattern = re.compile(r'^第\s*(\d+)\s*章\s*-\s*\[?(.*?)\]?$')
    role_pattern = re.compile(r'^本章定位：\s*\[?(.*)\]?$')
    purpose_pattern = re.compile(r'^核心作用：\s*\[?(.*)\]?$')
    suspense_pattern = re.compile(r'^悬念密度：\s*\[?(.*)\]?$')
    foreshadow_pattern = re.compile(r'^伏笔操作：\s*\[?(.*)\]?$')
    twist_pattern = re.compile(r'^认知颠覆：\s*\[?(.*)\]?$')
    summary_pattern = re.compile(r'^本章简述：\s*\[?(.*)\]?$')

    for chunk in chunks:
        lines = chunk.strip().splitlines()
        if not lines:
            continue
        header_match = chapter_number_pattern.match(lines[0].strip())
        if not header_match:
            continue
        chapter_number = int(header_match.group(1))
        chapter_title = header_match.group(2).strip()

        chapter_role = chapter_purpose = suspense_level = ""
        foreshadowing = plot_twist_level = chapter_summary = ""

        for line in lines[1:]:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            for pattern, key in [
                (role_pattern, "role"),
                (purpose_pattern, "purpose"),
                (suspense_pattern, "suspense"),
                (foreshadow_pattern, "foreshadow"),
                (twist_pattern, "twist"),
                (summary_pattern, "summary"),
            ]:
                m = pattern.match(line_stripped)
                if m:
                    val = m.group(1).strip()
                    if key == "role":
                        chapter_role = val
                    elif key == "purpose":
                        chapter_purpose = val
                    elif key == "suspense":
                        suspense_level = val
                    elif key == "foreshadow":
                        foreshadowing = val
                    elif key == "twist":
                        plot_twist_level = val
                    elif key == "summary":
                        chapter_summary = val
                    break

        results.append({
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_role": chapter_role,
            "chapter_purpose": chapter_purpose,
            "suspense_level": suspense_level,
            "foreshadowing": foreshadowing,
            "plot_twist_level": plot_twist_level,
            "chapter_summary": chapter_summary,
        })

    results.sort(key=lambda x: x["chapter_number"])
    return results


async def generate_directory(
    project: Project,
    architecture_text: str,
    user_guidance: str = "",
) -> tuple[str, list[dict]]:
    """
    章节目录生成。
    返回：(directory_text, parsed_chapters)
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API key not configured")

    adapter = create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )

    number_of_chapters = project.num_chapters or 10

    logger.info("Generating chapter blueprint ...")
    prompt = chapter_blueprint_prompt.format(
        novel_architecture=architecture_text,
        number_of_chapters=number_of_chapters,
        user_guidance=user_guidance,
    )
    directory_text = await _invoke_with_retry(adapter, prompt)
    if not directory_text:
        raise RuntimeError("chapter_blueprint_prompt generation failed")

    parsed_chapters = parse_chapter_blueprint(directory_text)
    logger.info(f"Directory generation completed: {len(parsed_chapters)} chapters parsed.")
    return directory_text, parsed_chapters


async def update_character_state(
    chapter_text: str,
    old_state: str,
) -> str:
    """
    根据新完成的章节文本更新角色状态。
    返回：更新后的角色状态文档全文。
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API key not configured")

    adapter = create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )

    prompt = update_character_state_prompt.format(
        chapter_text=chapter_text,
        old_state=old_state,
    )
    logger.info("Updating character state ...")
    new_state = await _invoke_with_retry(adapter, prompt)
    if not new_state:
        raise RuntimeError("update_character_state generation failed")
    return new_state


async def generate_chapter_draft(
    project: Project,
    chapter_num: int,
    architecture_text: str,
    directory_text: str,
    character_state_text: str = "",
    previous_chapter_draft: str | None = None,
    previous_chapter_summary: str = "",
) -> str:
    """
    单章正文生成。
    返回：draft_text
    """
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API key not configured")

    adapter = create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )

    parsed_chapters = parse_chapter_blueprint(directory_text)
    current_chapter = None
    for ch in parsed_chapters:
        if ch["chapter_number"] == chapter_num:
            current_chapter = ch
            break
    if not current_chapter:
        raise RuntimeError(f"Chapter {chapter_num} not found in directory")

    word_number = project.word_number or 2000

    if chapter_num == 1:
        logger.info(f"Generating chapter {chapter_num} draft (first chapter) ...")
        prompt = first_chapter_draft_prompt.format(
            novel_setting=architecture_text,
            character_state=character_state_text or "（暂无角色状态记录）",
            chapter_title=current_chapter["chapter_title"],
            chapter_summary=current_chapter["chapter_summary"],
            word_number=word_number,
        )
    else:
        logger.info(f"Generating chapter {chapter_num} draft ...")
        excerpt = ""
        if previous_chapter_draft:
            excerpt = previous_chapter_draft[-1500:]
        prompt = next_chapter_draft_prompt.format(
            novel_setting=architecture_text,
            character_state=character_state_text,
            previous_chapter_summary=previous_chapter_summary or "（暂无前一章概要）",
            previous_chapter_excerpt=excerpt,
            chapter_number=chapter_num,
            chapter_title=current_chapter["chapter_title"],
            chapter_summary=current_chapter["chapter_summary"],
            word_number=word_number,
        )

    draft_text = await _invoke_with_retry(adapter, prompt)
    if not draft_text:
        raise RuntimeError("Chapter draft generation failed")
    return draft_text
