# generation_service.py
# -*- coding: utf-8 -*-
"""
小说生成服务：复用 AI_NovelGenerator 核心逻辑，改造为异步 + 数据库驱动
"""

import json
import logging
import uuid

from app.core.config import settings
from app.generator.llm_adapter import create_llm_adapter
from app.generator.llm_utils import repair_stray_quotes
from sqlalchemy.ext.asyncio import AsyncSession
import re

from app.generator.block_library import build_context
from app.generator.genre_methodology import _render_genre_methodology, _render_hook_preference
from app.generator.prompts import (
    architecture_consistency_prompt,
    calm_build_state_summary_suffix,
    calm_extract_world_state_suffix,
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
from app.generator.structure_guidance import CALM_STRUCTURES, build_structure_guidance
from app.models.project import Project, ProjectAsset

logger = logging.getLogger(__name__)


# 用户未填写剧情走向时的占位符兜底文本，保证 prompt 的【创作意图】段始终有内容、不悬空
_NO_CREATIVE_INTENT_PLACEHOLDER = "（用户未填写创作意图）"


def _prompt_context_for_project(project: Project) -> tuple[str, str]:
    """
    从 project.writing_config 提取 prompt 注入内容。

    返回 (writing_context, creative_intent)：
    - writing_context：由积木库 build_context 把用户各维度选择拼成的「写作上下文」。
    - creative_intent：用户填写的剧情走向，作为高优先「创作意图」；
      未填写（缺失 / 非字符串 / 空白）时回退为占位符兜底文本，避免【创作意图】段悬空。

    旧项目没有 writing_config 时 writing_context 回退为空串，生成行为与改造前一致；
    creative_intent 一律返回占位符兜底文本，保证各生成 prompt 的【创作意图】段不悬空。
    """
    writing_config = getattr(project, "writing_config", None)
    if not isinstance(writing_config, dict):
        return "", _NO_CREATIVE_INTENT_PLACEHOLDER
    writing_context = build_context(writing_config)
    creative_intent = writing_config.get("plot_direction")
    if not isinstance(creative_intent, str) or not creative_intent.strip():
        return writing_context, _NO_CREATIVE_INTENT_PLACEHOLDER
    return writing_context, creative_intent.strip()


def _structure_for_project(project: Project) -> str | None:
    """
    从 project.writing_config 读取叙事结构。

    返回 str（结构名，如「日常流」）；无 writing_config / 非字符串 / 空白 → None。
    调用方以 None 传入 build_structure_guidance 即回退危机基线（旧项目行为不变）。
    """
    writing_config = getattr(project, "writing_config", None)
    if not isinstance(writing_config, dict):
        return None
    structure = writing_config.get("structure")
    if not isinstance(structure, str) or not structure.strip():
        return None
    return structure.strip()


def _make_adapter(temperature: float, llm_config: dict | None = None) -> object:
    """Create LLM adapter from user config or platform defaults."""
    if llm_config:
        return create_llm_adapter(
            interface_format=llm_config["interface_format"],
            base_url=llm_config["base_url"],
            model_name=llm_config["model"],
            api_key=llm_config["api_key"],
            temperature=temperature,
            max_tokens=llm_config["max_tokens"],
            timeout=llm_config["timeout"],
        )
    return create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=temperature,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )


async def _invoke_with_retry(adapter, prompt: str, max_retries: int = 3) -> str:
    """调用 LLM，带重试和输出清洗（仅去除首尾 markdown 代码块标记，保留正文内容）"""
    for attempt in range(max_retries):
        try:
            result = await adapter.invoke(prompt)
            cleaned = result.strip()
            # 精确去除首尾的 markdown 代码块标记（如 ```json ... ```），保留中间所有内容
            cleaned = re.sub(r"^```[\w]*\n?", "", cleaned)
            cleaned = re.sub(r"\n?```\s*$", "", cleaned)
            cleaned = cleaned.strip()
            if cleaned:
                return cleaned
            logger.warning(f"Empty response on attempt {attempt + 1}")
        except Exception as e:
            logger.warning(f"LLM invoke failed on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise
    return ""


def _current_content_section(current_content: str, asset_name: str) -> str:
    """构造「参考当前版本」prompt 段；无当前内容时返回空串（不占 prompt）。"""
    text = (current_content or "").strip()
    if not text:
        return ""
    return (
        f"【参考当前版本】\n"
        f"以下是当前已有的{asset_name}全文，请基于它优化：保留其合理设定，"
        f"针对作者要求调整，不要从零重写、不要丢失已有核心设定。\n\n"
        f"{text}"
    )


async def generate_architecture(
    project: Project,
    user_guidance: str = "",
    current_content: str = "",
    llm_config: dict | None = None,
) -> tuple[str, str]:
    """
    5 步架构生成 pipeline。
    返回：(architecture_text, character_state_text)
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        raise RuntimeError("LLM API key not configured")

    adapter = _make_adapter(temperature=0.3, llm_config=llm_config)

    writing_context, creative_intent = _prompt_context_for_project(project)
    guidance = build_structure_guidance(_structure_for_project(project))
    current_section = _current_content_section(current_content, "架构")

    # Step 1: Core seed
    prompt = core_seed_prompt.format(
        topic=project.topic or "",
        genre=project.genre or "",
        number_of_chapters=project.num_chapters or 10,
        word_number=project.word_number or 2000,
        writing_context=writing_context,
        creative_intent=creative_intent,
        structure_seed_guidance=guidance["seed"],
        current_content_section=current_section,
    )
    core_seed = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 1/5: Core seed generated")

    # Step 2: Character dynamics
    prompt = character_dynamics_prompt.format(
        user_guidance=user_guidance or "",
        core_seed=core_seed,
        writing_context=writing_context,
        creative_intent=creative_intent,
        structure_character_guidance=guidance["character"],
        current_content_section=current_section,
    )
    character_dynamics = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 2/5: Character dynamics generated")

    # Step 3: World building
    prompt = world_building_prompt.format(
        user_guidance=user_guidance or "",
        core_seed=core_seed,
        writing_context=writing_context,
        creative_intent=creative_intent,
        structure_world_guidance=guidance["world"],
        current_content_section=current_section,
    )
    world_building = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 3/5: World building generated")

    # Step 4: Plot architecture
    prompt = plot_architecture_prompt.format(
        user_guidance=user_guidance or "",
        core_seed=core_seed,
        character_dynamics=character_dynamics,
        world_building=world_building,
        writing_context=writing_context,
        creative_intent=creative_intent,
        current_content_section=current_section,
    )
    plot_architecture = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 4/5: Plot architecture generated")

    # Combine architecture text
    architecture_text = (
        f"【核心种子】\n{core_seed}\n\n"
        f"【角色动力学】\n{character_dynamics}\n\n"
        f"【世界观】\n{world_building}\n\n"
        f"【情节架构】\n{plot_architecture}"
    )

    # Step 5: Character state
    prompt = create_character_state_prompt.format(
        character_dynamics=character_dynamics,
        writing_context=writing_context,
        creative_intent=creative_intent,
    )
    character_state = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 5/5: Character state generated")

    return architecture_text, character_state


async def generate_directory(
    project: Project,
    architecture_text: str = "",
    user_guidance: str = "",
    current_content: str = "",
    llm_config: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    生成章节目录并解析。
    返回：(directory_text, parsed_chapters)
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        raise RuntimeError("LLM API key not configured")

    adapter = _make_adapter(temperature=0.3, llm_config=llm_config)

    writing_context, creative_intent = _prompt_context_for_project(project)
    guidance = build_structure_guidance(_structure_for_project(project))
    current_section = _current_content_section(current_content, "目录")

    prompt = chapter_blueprint_prompt.format(
        user_guidance=user_guidance or "",
        novel_architecture=architecture_text or "",
        number_of_chapters=project.num_chapters or 10,
        writing_context=writing_context,
        creative_intent=creative_intent,
        structure_blueprint_guidance=guidance["blueprint"],
        current_content_section=current_section,
    )
    directory_text = await _invoke_with_retry(adapter, prompt)
    if not directory_text:
        raise RuntimeError("Directory generation failed")

    parsed_chapters = parse_chapter_blueprint(directory_text)
    if not parsed_chapters:
        raise RuntimeError(
            f"Directory parsing failed: no chapters extracted from LLM output. "
            f"Raw output preview: {directory_text[:500]}"
        )
    if len(parsed_chapters) != project.num_chapters:
        logger.warning(
            f"Directory parsing mismatch: expected {project.num_chapters} chapters, "
            f"got {len(parsed_chapters)}. This may indicate format issues in LLM output."
        )
    logger.info(f"Directory generation completed: {len(parsed_chapters)} chapters parsed.")
    return directory_text, parsed_chapters


def parse_chapter_blueprint(text: str) -> list[dict]:
    """
    解析章节蓝图文本，支持多种标题格式：
    - 第1章 - [标题]
    - 第1章 [标题]
    - 第1章：标题
    - Chapter 1
    """
    chapters = []

    # 匹配 "第n章 - 标题" 或 "第n章 标题" 或 "第n章：标题"
    patterns = [
        r"第\s*(\d+)\s*章\s*[-–—]\s*(.+?)(?=第\s*\d+\s*章|\Z)",
        r"第\s*(\d+)\s*章\s+(.+?)(?=第\s*\d+\s*章|\Z)",
        r"第\s*(\d+)\s*章[：:]\s*(.+?)(?=第\s*\d+\s*章|\Z)",
        r"Chapter\s+(\d+)\s*[-–—]?\s*(.+?)(?=Chapter\s+\d+|\Z)",
    ]

    for pattern in patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
        if matches:
            for m in matches:
                chapter_num = int(m.group(1))
                # 提取标题（取第一行或第一个有意义的短语）
                title_block = m.group(2).strip()
                title_lines = [l.strip() for l in title_block.splitlines() if l.strip()]
                title = title_lines[0] if title_lines else f"第{chapter_num}章"
                # 清理标题中可能的后续字段
                title = re.split(r"[\n\r]", title)[0].strip()
                title = re.sub(r"^(本章定位|核心作用|悬念密度|伏笔操作|认知颠覆|本章简述)[：:]", "", title).strip()

                chapters.append({
                    "chapter_number": chapter_num,
                    "chapter_title": title,
                    "chapter_summary": "",
                })
            if chapters:
                break

    # 按章节号排序
    chapters.sort(key=lambda x: x["chapter_number"])
    return chapters


async def update_character_state(
    chapter_text: str,
    old_state: str,
    llm_config: dict | None = None,
) -> str:
    """
    根据新完成的章节文本更新角色状态。
    返回：更新后的角色状态文档全文。
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        raise RuntimeError("LLM API key not configured")

    adapter = _make_adapter(temperature=0.3, llm_config=llm_config)

    prompt = update_character_state_prompt.format(
        chapter_text=chapter_text,
        old_state=old_state,
    )
    logger.info("Updating character state ...")
    new_state = await _invoke_with_retry(adapter, prompt)
    if not new_state:
        raise RuntimeError("update_character_state generation failed")
    return new_state


# =================== P2-B 角色卡系统 ===================
async def _load_character_asset(db: AsyncSession, project_id) -> ProjectAsset | None:
    """读取 characters 资产记录（含 content_json / content_text）。"""
    from sqlalchemy import select
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project_id),
            ProjectAsset.asset_type == "characters",
        )
    )
    return result.scalar_one_or_none()


def _render_character_cards(characters_json, active_names=None) -> str:
    """把角色卡 JSON 渲染为可读文本（供 prompt 注入 / content_text 兼容存储）。

    active_names 给定则只渲染出场角色；None 渲染全部。非 dict / 缺字段时优雅降级。
    """
    chars = characters_json.get("characters") if isinstance(characters_json, dict) else None
    if not isinstance(chars, dict):
        return ""
    lines = []
    for name, card in chars.items():
        if active_names and name not in active_names:
            continue
        if not isinstance(card, dict):
            lines.append(f"### {name}")
            lines.append("")
            continue
        lines.append(f"### {name}")
        profile = card.get("profile")
        if isinstance(profile, str) and profile.strip():
            lines.append(f"- 人设：{profile.strip()}")
        state = card.get("current_state")
        if isinstance(state, dict) and state:
            lines.append("- 当前状态：" + "；".join(f"{k}：{v}" for k, v in state.items() if str(v).strip()))
        relations = card.get("relations")
        if isinstance(relations, dict) and relations:
            lines.append("- 关系：" + "；".join(f"{k}：{v}" for k, v in relations.items() if str(v).strip()))
        known = card.get("known")
        if isinstance(known, list) and known:
            lines.append("- 认知：" + "；".join(str(x) for x in known if str(x).strip()))
        trajectory = card.get("trajectory")
        if isinstance(trajectory, list) and trajectory:
            lines.append("- 轨迹：" + "；".join(str(x) for x in trajectory if str(x).strip()))
        last_appearance = card.get("last_appearance")
        if last_appearance is not None:
            lines.append(f"- 最近出场：第{last_appearance}章")
        lines.append("")
    return "\n".join(lines).strip()


async def _active_character_names(db: AsyncSession, project_id, prev_chapter_num: int, cards: dict) -> list[str]:
    """从上一章 actual_summary_json.characters 提取出场角色名，与现有角色卡取交集。"""
    from app.models.project import Chapter
    from sqlalchemy import select
    result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == str(project_id),
            Chapter.chapter_num == prev_chapter_num,
        )
    )
    prev = result.scalar_one_or_none()
    if not prev:
        return []
    memory = getattr(prev, "actual_summary_json", None)
    names = memory.get("characters") if isinstance(memory, dict) else None
    if not isinstance(names, list):
        return []
    chars = cards.get("characters") if isinstance(cards, dict) else {}
    return [n for n in names if isinstance(n, str) and n in chars]


async def load_active_character_cards(
    db: AsyncSession,
    project_id,
    chapter_num: int,
) -> str:
    """写前只加载「出场角色卡」，防止角色状态随章节数增长导致上下文稀释。

    优先级：
    1. characters 资产有 content_json（结构化角色卡）→ 只渲染出场角色
       （出场名单取上一章 actual_summary_json.characters，与现有卡片取交集）。
    2. 无法确定出场角色（第 1 章 / 上一章无 characters 记录）→ 渲染全部卡片兜底，防上下文缺失。
    3. 旧项目（无 content_json，characters 为文本）→ 原样返回 content_text（与改造前行为一致，不崩溃）。
    """
    asset = await _load_character_asset(db, project_id)
    if asset is None:
        return ""
    if not asset.content_json:
        return asset.content_text or ""
    cards = asset.content_json
    active_names: list[str] = []
    if chapter_num and chapter_num > 1:
        active_names = await _active_character_names(db, project_id, chapter_num - 1, cards)
    if not active_names:
        return _render_character_cards(cards)
    return _render_character_cards(cards, active_names)


async def update_character_cards(
    db: AsyncSession,
    project_id,
    chapter_num: int,
    chapter_text: str,
    llm_config: dict | None = None,
) -> dict | None:
    """根据本章正文更新角色卡档案，写回 characters 资产（双通道）。

    - content_json = 结构化角色卡；content_text = 可读渲染（供 drama / 导出 / 前端兼容，避免格式变更破坏既有功能）。
    - 输入兼容：旧版文本角色状态（content_text）或结构化角色卡 JSON（content_json），首次更新时自动迁移。
    - 失败 / 未配置 LLM / 空正文：返回 None（保留旧状态，不抛异常，不中断生成）。
    """
    if not chapter_text:
        return None
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return None

    asset = await _load_character_asset(db, project_id)
    old_state = asset.content_json if (asset and asset.content_json) else (asset.content_text if asset else "")

    try:
        from app.generator.prompts import character_card_update_prompt
        adapter = _make_adapter(temperature=0.2, llm_config=llm_config)
        old_repr = json.dumps(old_state, ensure_ascii=False, indent=2) if isinstance(old_state, dict) else (old_state or "")
        prompt = character_card_update_prompt.format(
            chapter_text=chapter_text[:4000],  # 截断防止超限
            old_state=old_repr,
        )
        logger.info(f"Updating character cards for chapter {chapter_num} ...")
        raw = await _invoke_with_retry(adapter, prompt)
    except Exception as e:
        logger.warning(f"Character card update failed for chapter {chapter_num}: {e}")
        return None

    if not raw:
        return None
    cards = _parse_llm_json(raw)
    if not cards or not isinstance(cards.get("characters"), dict):
        logger.warning(f"Failed to parse character cards JSON for chapter {chapter_num}")
        return None

    # 规范化 last_appearance：缺失即视为"本章出场"→ 用本章号。
    # （prompt 要求未出场卡片"原样保留"，正常会带原 last_appearance；缺失多为新增/更新卡片漏填。）
    new_chars = cards["characters"]
    for name, new_card in new_chars.items():
        if isinstance(new_card, dict) and new_card.get("last_appearance") is None:
            new_card["last_appearance"] = chapter_num

    text = _render_character_cards(cards)
    if asset:
        asset.content_json = cards
        asset.content_text = text
        asset.version += 1
    else:
        asset = ProjectAsset(
            project_id=str(project_id),
            asset_type="characters",
            content_text=text,
            content_json=cards,
        )
        db.add(asset)
    await db.commit()
    logger.info(f"Character cards saved for chapter {chapter_num} ({len(cards['characters'])} cards)")
    return cards


def _chapter_excerpt(draft: str | None) -> str:
    """取章节结尾做衔接上下文：结尾 20%，下限 800 字，上限 2000 字。"""
    if not draft:
        return ""
    length = len(draft)
    if length <= 800:
        return draft
    window = max(800, min(2000, int(length * 0.2)))
    return draft[-window:]


async def generate_chapter_draft(
    project: Project,
    chapter_num: int,
    architecture_text: str,
    directory_text: str,
    character_state_text: str = "",
    previous_chapter_draft: str | None = None,
    previous_chapter_summary: str = "",
    world_state_summary: str = "",
    llm_config: dict | None = None,
) -> str:
    """
    单章正文生成。
    返回：draft_text
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        raise RuntimeError("LLM API key not configured")

    adapter = _make_adapter(temperature=0.3, llm_config=llm_config)

    parsed_chapters = parse_chapter_blueprint(directory_text)
    current_chapter = None
    for ch in parsed_chapters:
        if ch["chapter_number"] == chapter_num:
            current_chapter = ch
            break
    if not current_chapter:
        raise RuntimeError(f"Chapter {chapter_num} not found in directory")

    word_number = project.word_number or 2000
    writing_context, creative_intent = _prompt_context_for_project(project)
    guidance = build_structure_guidance(_structure_for_project(project))
    genre_methodology = _render_genre_methodology(project.genre or "")

    if chapter_num == 1:
        logger.info(f"Generating chapter {chapter_num} draft (first chapter) ...")
        prompt = first_chapter_draft_prompt.format(
            novel_setting=architecture_text,
            character_state=character_state_text or "（暂无角色状态记录）",
            world_state_summary=world_state_summary or "（暂无世界状态摘要）",
            chapter_title=current_chapter["chapter_title"],
            chapter_summary=current_chapter["chapter_summary"],
            word_number=word_number,
            writing_context=writing_context,
            creative_intent=creative_intent,
            genre_methodology=genre_methodology,
            structure_first_chapter_guidance=guidance["first_chapter"],
        )
    else:
        logger.info(f"Generating chapter {chapter_num} draft ...")
        excerpt = _chapter_excerpt(previous_chapter_draft)
        prompt = next_chapter_draft_prompt.format(
            novel_setting=architecture_text,
            character_state=character_state_text or "（暂无角色状态记录）",
            world_state_summary=world_state_summary or "（暂无世界状态摘要）",
            previous_chapter_summary=previous_chapter_summary or "（暂无前一章概要）",
            previous_chapter_excerpt=excerpt,
            chapter_number=chapter_num,
            chapter_title=current_chapter["chapter_title"],
            chapter_summary=current_chapter["chapter_summary"],
            word_number=word_number,
            writing_context=writing_context,
            creative_intent=creative_intent,
            genre_methodology=genre_methodology,
            structure_chapter_guidance=guidance["chapter"],
            hook_preference=_render_hook_preference(project.genre or ""),
        )

    draft_text = await _invoke_with_retry(adapter, prompt)
    if not draft_text:
        raise RuntimeError("Chapter draft generation failed")
    return draft_text


def _parse_llm_json(content: str) -> dict | None:
    """从 LLM 返回的文本中提取 JSON，支持 markdown code block"""
    import json
    if not content or not isinstance(content, str):
        return None
    cleaned = content.strip()
    # 去掉开头的 json 标记
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()
    candidates = [cleaned]
    # 提取 ```json ... ```
    m = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if m:
        candidates.append(m.group(1).strip())
    # 提取花括号内容
    m = re.search(r'\{[\s\S]*\}', cleaned)
    if m:
        candidates.append(m.group().strip())
    # 兜底：修复字符串内部未转义的双引号（LLM 在台词/描述字段内嵌英文引号）
    repaired = repair_stray_quotes(cleaned)
    if repaired != cleaned:
        candidates.append(repaired)
        m = re.search(r'\{[\s\S]*\}', repaired)
        if m:
            candidates.append(m.group().strip())
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return None


async def extract_world_state_delta(
    chapter_text: str,
    chapter_number: int,
    current_state: dict,
    template: dict,
    llm_config: dict | None = None,
    structure: str | None = None,
) -> dict:
    """
    从章节文本中提取世界状态变化（Delta）。
    返回：结构化 delta dict

    structure 为平静结构（日常流/群像交织）时追加中性化约束：
    除变化外保留仍有意义的常态状态（主角身份、稳定关系、重要场所），不当作变化丢弃。
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return {"changed_in_chapter": chapter_number, "no_changes": True}

    from app.generator.prompts import extract_world_state_delta_prompt

    adapter = _make_adapter(temperature=0.2, llm_config=llm_config)

    prompt = extract_world_state_delta_prompt.format(
        current_state=json.dumps(current_state, ensure_ascii=False, indent=2),
        template_description=template.get("description", ""),
        chapter_number=chapter_number,
        chapter_text=chapter_text[:4000],  # 截断防止超限
    )
    if structure and structure.strip() in CALM_STRUCTURES:
        prompt += calm_extract_world_state_suffix
    logger.info(f"Extracting world state delta for chapter {chapter_number} ...")
    raw = await _invoke_with_retry(adapter, prompt)
    if not raw:
        return {"changed_in_chapter": chapter_number, "no_changes": True}

    delta = _parse_llm_json(raw)
    if not delta:
        logger.warning(f"Failed to parse world state delta JSON for chapter {chapter_number}")
        return {"changed_in_chapter": chapter_number, "no_changes": True}

    return delta


async def extract_chapter_memory(
    db: AsyncSession,
    chapter,
    llm_config: dict | None = None,
) -> dict:
    """
    从章节正文提取结构化记忆，供后续章节保持连贯。

    返回 dict：summary / hook / characters / relations_changed / foreshadowing_added（含 known_by）
    / foreshadowing_touched / foreshadowing_recovered / subplot_advanced / connects_to。
    - 成功：LLM 返回的结构化 JSON（V3 P3-B 起对缺失的伏笔/副线字段补齐空列表，便于台账合并）。
    - 失败：返回空 dict {}（LLM 未配置 / 调用异常 / 返回空 / JSON 解析失败 / summary 缺失），
      调用方不写入 actual_summary_json，下一章自动回退 outline（符合 spec 回退链设计）。
    - db 参数按接口保留（当前未使用，供后续扩展）。

    调用方仅在返回 dict 含可用 summary 时才写入 chapter.actual_summary_json。
    """
    draft = getattr(chapter, "draft", None) or ""
    if not draft:
        return {}

    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return {}

    try:
        from app.generator.prompts import chapter_memory_extract_prompt

        adapter = _make_adapter(temperature=0.2, llm_config=llm_config)
        prompt = chapter_memory_extract_prompt.format(chapter_text=draft[:4000])  # 截断防止超限
        logger.info(f"Extracting chapter memory for chapter {getattr(chapter, 'chapter_num', '?')} ...")
        raw = await _invoke_with_retry(adapter, prompt)
    except Exception as e:
        logger.warning(f"Chapter memory extraction failed: {e}")
        return {}

    if not raw:
        return {}

    memory = _parse_llm_json(raw)
    if not memory:
        logger.warning("Failed to parse chapter memory JSON, falling back to outline")
        return {}

    # summary 缺失或为空时视为提取失败：返回空 dict，不持久化原文片段
    if not isinstance(memory.get("summary"), str) or not memory["summary"].strip():
        logger.warning("Chapter memory missing summary, falling back to outline")
        return {}

    # V3 P3-B：规范化伏笔/副线字段，容忍缺失（旧输出兼容）。
    # 台账合并（merge_foreshadowing_delta）对缺失字段按「无变化」跳过，这里置空列表便于统一消费。
    for key in ("foreshadowing_touched", "foreshadowing_recovered", "subplot_advanced", "foreshadowing_added"):
        if key not in memory or not isinstance(memory[key], list):
            memory[key] = []
    return memory


async def build_arc_summary(
    chapters: list,
    llm_config: dict | None = None,
    arc_size: int | None = None,
) -> dict:
    """
    在 arc 边界合成 arc 级摘要（V3 P3-B 记忆分层 L2）。

    输入：本 arc 的 Chapter 对象列表（含 actual_summary_json.summary）。
    返回：
      - 成功：{"summary": "<arc 摘要文本>", "chapter_range": [start, end]}
      - 失败：{}（未配置 / 调用异常 / 返回空 / 无可用章节记忆），调用方不写入资产。
    只在 arc 边界调用，摊薄成本 = 1/N 次/章，不在逐章热路径。
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return {}

    # 收集本 arc 各章已提取的结构化记忆摘要（summary 非空才可用），保留真实章节号
    chapter_memories: list[tuple[int, str]] = []
    for ch in chapters:
        mem = getattr(ch, "actual_summary_json", None)
        if not isinstance(mem, dict):
            continue
        summary = mem.get("summary")
        if isinstance(summary, str) and summary.strip():
            num = getattr(ch, "chapter_num", None)
            chapter_memories.append((num if isinstance(num, int) else len(chapter_memories) + 1, summary.strip()))

    if not chapter_memories:
        return {}

    try:
        from app.generator.prompts import build_arc_summary_prompt

        adapter = _make_adapter(temperature=0.2, llm_config=llm_config)
        chapters_memory = "\n\n".join(
            f"第{num}章记忆：{s}" for num, s in chapter_memories
        )
        prompt = build_arc_summary_prompt.format(
            arc_size=arc_size or 15,
            chapters_memory=chapters_memory,
        )
        logger.info("Building arc summary ...")
        raw = await _invoke_with_retry(adapter, prompt)
    except Exception as e:
        logger.warning(f"Arc summary build failed: {e}")
        return {}

    if not raw or not raw.strip():
        return {}

    nums = []
    for ch in chapters:
        n = getattr(ch, "chapter_num", None)
        if isinstance(n, int):
            nums.append(n)
    chapter_range = [min(nums), max(nums)] if nums else []
    return {"summary": raw.strip(), "chapter_range": chapter_range}


async def synthesize_book_summary(
    arcs: list,
    llm_config: dict | None = None,
) -> str:
    """
    由已冻结的各 arc 摘要合成全书摘要（V3 P3-B 记忆分层 L3）。

    输入：arcs（list[dict]，每项含 summary）。
    返回：全书摘要文本；失败（未配置 / 调用异常 / 返回空 / 无可用 arc 摘要）返回 ""。
    在 arc 边界每完成一个 arc 后增量刷新一次。
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return ""

    arc_summaries = []
    for arc in arcs:
        if not isinstance(arc, dict):
            continue
        s = arc.get("summary")
        if isinstance(s, str) and s.strip():
            arc_summaries.append(s.strip())

    if not arc_summaries:
        return ""

    try:
        from app.generator.prompts import synthesize_book_summary_prompt

        adapter = _make_adapter(temperature=0.2, llm_config=llm_config)
        prompt = synthesize_book_summary_prompt.format(
            arcs_summary="\n\n".join(arc_summaries),
        )
        logger.info("Synthesizing book summary ...")
        raw = await _invoke_with_retry(adapter, prompt)
    except Exception as e:
        logger.warning(f"Book summary synthesis failed: {e}")
        return ""

    return raw.strip() if raw else ""


def merge_world_state(old_state: dict, delta: dict) -> dict:
    """
    将 delta 合并到旧 world_state 中。
    返回：更新后的 world_state
    """
    import copy
    state = copy.deepcopy(old_state)
    # 记录变更历史
    chapter_num = delta.get("changed_in_chapter")
    if "history" not in state:
        state["history"] = []

    if delta.get("no_changes"):
        state["history"].append({"chapter": chapter_num, "changes": []})
        return state

    changed = []
    # 深拷贝 delta 避免修改传入的参数
    delta_copy = copy.deepcopy(delta)
    for category in ["characters", "events", "world"]:
        if category not in delta_copy:
            continue
        delta_cat = delta_copy[category]
        if not isinstance(delta_cat, dict):
            continue
        if category not in state:
            state[category] = {}

        # 扁平结构（如 world）：整体为「字段 -> 值」，无实体层级
        if "changed_fields" in delta_cat:
            fields = {k: v for k, v in delta_cat.items() if k != "changed_fields"}
            for field, new_val in fields.items():
                old_val = state[category].get(field)
                if old_val != new_val:
                    changed.append({
                        "chapter": chapter_num,
                        "category": category,
                        "entity": category,
                        "field": field,
                        "from": old_val,
                        "to": new_val,
                    })
                state[category][field] = new_val
            continue

        # 嵌套结构（characters / events）：实体名 -> 字段
        for key, fields in delta_cat.items():
            if not isinstance(fields, dict):
                continue
            if key not in state[category]:
                state[category][key] = {}
            changed_fields = fields.pop("changed_fields", [])
            for field, new_val in fields.items():
                if field == "changed_fields":
                    continue
                old_val = state[category][key].get(field)
                if old_val != new_val:
                    changed.append({
                        "chapter": chapter_num,
                        "category": category,
                        "entity": key,
                        "field": field,
                        "from": old_val,
                        "to": new_val,
                    })
                state[category][key][field] = new_val

    state["history"].append({"chapter": chapter_num, "changes": changed})
    return state


async def build_state_summary(
    world_state: dict,
    target_chapter: int,
    chapter_title: str,
    chapter_summary: str,
    llm_config: dict | None = None,
    structure: str | None = None,
) -> str:
    """
    为后续章节生成提取最相关的世界状态摘要。
    返回：摘要文本（条目列表）

    structure 为平静结构（日常流/群像交织）时：
    - slim_state 放宽裁剪（每类保留上限 20 条、变更窗口 5 章），让「稳定关系/常态状态」
      这类跨章常态条目不易被最近变更挤掉；
    - 摘要 prompt 追加中性化约束：同时保留当前舒适/日常状态与情绪基调。
    危机结构与缺省行为不变（每类 10 条 / 3 章窗口）。
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return ""

    from app.generator.prompts import build_state_summary_prompt

    adapter = _make_adapter(temperature=0.2, llm_config=llm_config)

    is_calm = structure is not None and structure.strip() in CALM_STRUCTURES
    # 精简 world_state 减少 token；平静结构放宽裁剪，保留更多常态条目
    max_items = 20 if is_calm else 10
    recent_window = 5 if is_calm else 3
    slim_state = {}
    for k, v in world_state.items():
        if k == "history":
            # 只保留最近 N 章变更记录
            slim_state[k] = v[-recent_window:] if isinstance(v, list) else v
        elif k in ("characters", "events", "world"):
            # 限制每类最多 max_items 个条目，防止 token 超限
            if isinstance(v, dict):
                items = list(v.items())
                if len(items) > max_items:
                    # 优先保留有变更历史的条目（最近 N 章内出现过）
                    recent_entities = set()
                    for h in world_state.get("history", [])[-recent_window:]:
                        for c in h.get("changes", []):
                            if c.get("category") == k:
                                recent_entities.add(c.get("entity"))
                    # 先保留最近有变更的，再按字母顺序补足到 max_items 个
                    prioritized = [(key, val) for key, val in items if key in recent_entities]
                    remaining = [(key, val) for key, val in items if key not in recent_entities]
                    slim_state[k] = dict(prioritized + remaining[: max(0, max_items - len(prioritized))])
                else:
                    slim_state[k] = v
            else:
                slim_state[k] = v
        else:
            slim_state[k] = v

    prompt = build_state_summary_prompt.format(
        world_state=json.dumps(slim_state, ensure_ascii=False, indent=2),
        target_chapter=target_chapter,
        chapter_title=chapter_title,
        chapter_summary=chapter_summary,
    )
    if is_calm:
        prompt += calm_build_state_summary_suffix
    logger.info(f"Building state summary for chapter {target_chapter} ...")
    result = await _invoke_with_retry(adapter, prompt)
    return result or ""


async def check_chapter_consistency(
    chapter_text: str,
    character_state_text: str,
    previous_chapter_draft: str | None = None,
    llm_config: dict | None = None,
) -> str:
    """
    审查新生成的章节是否与角色状态和前文情节一致。
    返回：检查结果文本（包含 CHECK: CONSISTENT 或 CHECK: INCONSISTENT）
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return "CHECK: CONSISTENT (LLM not configured)"

    from app.generator.prompts import chapter_consistency_check_prompt

    adapter = _make_adapter(temperature=0.2, llm_config=llm_config)

    excerpt = _chapter_excerpt(previous_chapter_draft) or "（无前一章）"
    prompt = chapter_consistency_check_prompt.format(
        character_state=character_state_text or "（未提供角色状态）",
        previous_chapter_excerpt=excerpt,
        chapter_text=chapter_text,
    )
    logger.info("Running chapter consistency check ...")
    result = await _invoke_with_retry(adapter, prompt)
    if not result:
        return "CHECK: CONSISTENT (check failed, non-blocking)"
    return result
