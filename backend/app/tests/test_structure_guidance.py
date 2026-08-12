# test_structure_guidance.py
# -*- coding: utf-8 -*-
"""V3 P3-A 去危机化：structure 条件化分片 + prompts 占位符改造 单元测试。"""

import re

from app.generator.prompts import (
    architecture_consistency_prompt,
    chapter_blueprint_prompt,
    character_dynamics_prompt,
    core_seed_prompt,
    first_chapter_draft_prompt,
    next_chapter_draft_prompt,
    world_building_prompt,
)
from app.generator.structure_guidance import (
    CALM_STRUCTURES,
    CRISIS_STRUCTURES,
    build_structure_guidance,
)

KEYS = {"seed", "character", "world", "first_chapter", "chapter", "blueprint"}

CRISIS_KEYWORDS = ["异常征兆", "打破平衡", "悬念曲线", "更大危机", "灾难后果", "张力对比"]
NEGATIONS = ["不强求", "不必", "不要求", "不强制", "无需", "不强调", "不刻意"]


def _positive_crisis(text):
    """找出 text 中「正向使用危机语义」的危机词。

    平静分片里危机词只允许出现在否定语境（不强求异常征兆 / 不必打破平衡 /
    不要求张力对比 等），故 12 字符前缀窗口内出现否定词则不算正向使用。
    """
    found = []
    for word in CRISIS_KEYWORDS:
        idx = 0
        while True:
            idx = text.find(word, idx)
            if idx == -1:
                break
            # 20 字符窗口：覆盖「不要求设计'灾难后果'或'隐藏更大危机'」这类
            # 否定词与被否定的危机词相隔较远的情况。
            before = text[max(0, idx - 20):idx]
            if not any(n in before for n in NEGATIONS):
                found.append(word)
            idx += len(word)
    return found


def test_classification_sets_complete():
    assert CRISIS_STRUCTURES == {"升级打怪", "三幕经典", "倒叙钩子", "单元剧快节奏", "长线连载"}
    assert CALM_STRUCTURES == {"日常流", "群像交织"}


def test_default_returns_crisis_baseline():
    g = build_structure_guidance(None)
    assert set(g.keys()) == KEYS
    for key in KEYS:
        assert g[key], key
    # 危机基线含危机特征词（行为与改造前一致）
    assert "打破平衡" in g["first_chapter"]
    assert "隐藏的更大危机" in g["seed"] or "更大危机" in g["seed"]


def test_unknown_structure_falls_back_to_crisis():
    g = build_structure_guidance("不存在的结构")
    assert g["first_chapter"] == build_structure_guidance(None)["first_chapter"]


def test_crisis_structures_use_crisis_baseline():
    for s in CRISIS_STRUCTURES:
        g = build_structure_guidance(s)
        assert g == build_structure_guidance(None), s


def test_calm_structures_are_de_crisis():
    for s in CALM_STRUCTURES:
        g = build_structure_guidance(s)
        assert set(g.keys()) == KEYS, s
        for key in KEYS:
            assert g[key], f"{s}.{key}"
        # 平静分片不「正向使用」危机语义（否定语境出现不算）
        signs = []
        for key in KEYS:
            signs += [(key, w) for w in _positive_crisis(g[key])]
        assert not signs, f"{s} 平静分片仍正向使用危机语义: {signs}"
        # 与危机基线确实不同（去危机化生效）
        assert g != build_structure_guidance(None), s


def test_calm_has_positive_feedback_semantics():
    g = build_structure_guidance("日常流")
    assert "生活切片" in g["first_chapter"]
    assert "日常" in g["world"] or "生活" in g["world"]
    assert "不强求" in g["chapter"] or "不要求" in g["chapter"]


def test_prompts_have_conditional_placeholders():
    """prompts.py 7 处硬危机规则已改条件占位符。"""
    assert "{structure_seed_guidance}" in core_seed_prompt
    assert "{structure_character_guidance}" in character_dynamics_prompt
    assert "{structure_world_guidance}" in world_building_prompt
    assert "{structure_first_chapter_guidance}" in first_chapter_draft_prompt
    assert "{structure_chapter_guidance}" in next_chapter_draft_prompt
    assert "{structure_blueprint_guidance}" in chapter_blueprint_prompt


def test_prompts_have_genre_methodology_and_hook():
    assert "{genre_methodology}" in first_chapter_draft_prompt
    assert "{genre_methodology}" in next_chapter_draft_prompt
    # 钩子四断法：next_chapter 含 {hook_preference} 与四类说明
    assert "{hook_preference}" in next_chapter_draft_prompt
    for label in ["决定：主角做了一个不可撤回的选择", "发现：对旧事实的一个新解释",
                  "误判：读者知道角色正走向错误答案", "代价：目标刚达成，更大账单出现"]:
        assert label in next_chapter_draft_prompt


def test_consistency_prompt_is_neutral():
    # 一致性校验不再要求"危机在架构中体现"
    assert "危机" not in architecture_consistency_prompt
    assert "创作意图" in architecture_consistency_prompt


def test_prompt_placeholders_all_formatable():
    """新占位符 + 既有占位符都能被 format（无残留未替换）。"""
    all_fields = {
        "structure_seed_guidance", "structure_character_guidance", "structure_world_guidance",
        "structure_first_chapter_guidance", "structure_chapter_guidance", "structure_blueprint_guidance",
        "genre_methodology", "hook_preference",
        # 既有字段（生成服务 format 时传入）
        "topic", "genre", "number_of_chapters", "word_number", "writing_context", "creative_intent",
        # 故事形态篇幅行（V3 P2 形态闭环，生成服务 format 时传入）
        "scope_statement",
        "user_guidance", "core_seed", "novel_setting", "character_state", "world_state_summary",
        "chapter_title", "chapter_summary", "previous_chapter_summary", "previous_chapter_excerpt",
        "chapter_number", "novel_architecture", "character_dynamics", "world_building",
        "plot_architecture",
        # 「参考当前版本」段（V3 P2 优化重新生成，生成服务 format 时传入）
        "current_content_section",
    }
    prompts = {
        "core_seed_prompt": core_seed_prompt,
        "character_dynamics_prompt": character_dynamics_prompt,
        "world_building_prompt": world_building_prompt,
        "first_chapter_draft_prompt": first_chapter_draft_prompt,
        "next_chapter_draft_prompt": next_chapter_draft_prompt,
        "chapter_blueprint_prompt": chapter_blueprint_prompt,
    }
    for name, text in prompts.items():
        placeholders = set(re.findall(r"\{([a-zA-Z0-9_]+)\}", text))
        missing = placeholders - all_fields
        assert not missing, f"{name} 有未知占位符: {missing}"
