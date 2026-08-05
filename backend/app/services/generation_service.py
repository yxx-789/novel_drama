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
from sqlalchemy.ext.asyncio import AsyncSession
import re

from app.generator.block_library import build_context
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


async def generate_architecture(
    project: Project,
    user_guidance: str = "",
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

    # Step 1: Core seed
    prompt = core_seed_prompt.format(
        topic=project.topic or "",
        genre=project.genre or "",
        number_of_chapters=project.num_chapters or 10,
        word_number=project.word_number or 2000,
        writing_context=writing_context,
        creative_intent=creative_intent,
    )
    core_seed = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 1/5: Core seed generated")

    # Step 2: Character dynamics
    prompt = character_dynamics_prompt.format(
        user_guidance=user_guidance or "",
        core_seed=core_seed,
        writing_context=writing_context,
        creative_intent=creative_intent,
    )
    character_dynamics = await _invoke_with_retry(adapter, prompt)
    logger.info("Architecture step 2/5: Character dynamics generated")

    # Step 3: World building
    prompt = world_building_prompt.format(
        user_guidance=user_guidance or "",
        core_seed=core_seed,
        writing_context=writing_context,
        creative_intent=creative_intent,
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

    prompt = chapter_blueprint_prompt.format(
        user_guidance=user_guidance or "",
        novel_architecture=architecture_text or "",
        number_of_chapters=project.num_chapters or 10,
        writing_context=writing_context,
        creative_intent=creative_intent,
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
) -> dict:
    """
    从章节文本中提取世界状态变化（Delta）。
    返回：结构化 delta dict
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

    返回 dict：summary / hook / characters / relations_changed / foreshadowing_added / connects_to。
    - 成功：LLM 返回的结构化 JSON。
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
    return memory


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
) -> str:
    """
    为后续章节生成提取最相关的世界状态摘要。
    返回：摘要文本（条目列表）
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        return ""

    from app.generator.prompts import build_state_summary_prompt

    adapter = _make_adapter(temperature=0.2, llm_config=llm_config)

    # 精简 world_state 减少 token
    slim_state = {}
    for k, v in world_state.items():
        if k == "history":
            # 只保留最近 3 章变更记录
            slim_state[k] = v[-3:] if isinstance(v, list) else v
        elif k in ("characters", "events", "world"):
            # 限制每类最多 10 个条目，防止 token 超限
            if isinstance(v, dict):
                items = list(v.items())
                if len(items) > 10:
                    # 优先保留有变更历史的条目（最近 3 章内出现过）
                    recent_entities = set()
                    for h in world_state.get("history", [])[-3:]:
                        for c in h.get("changes", []):
                            if c.get("category") == k:
                                recent_entities.add(c.get("entity"))
                    # 先保留最近有变更的，再按字母顺序补足到 10 个
                    prioritized = [(key, val) for key, val in items if key in recent_entities]
                    remaining = [(key, val) for key, val in items if key not in recent_entities]
                    slim_state[k] = dict(prioritized + remaining[: max(0, 10 - len(prioritized))])
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
