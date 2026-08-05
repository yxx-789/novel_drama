# test_block_library.py
# -*- coding: utf-8 -*-
"""积木库（用户层 7 维）单元测试。"""

import pytest

from app.generator.block_library import (
    AUDIENCE_BLOCKS,
    BACKGROUND_BLOCKS,
    CAST_SCALE_BLOCKS,
    CORE_GENRE_BLOCKS,
    CORE_GENRES,
    DEFAULT_RECIPES,
    DIMENSION_BLOCKS,
    DIMENSION_LABELS,
    DIMENSION_OPTIONS,
    DIMENSION_ORDER,
    HOOK_BLOCKS,
    STRUCTURE_BLOCKS,
    STYLE_BLOCKS,
    build_context,
)

MIN_FRAGMENT_LEN = 50

BLOCKS = {
    "core_genre": CORE_GENRE_BLOCKS,
    "background": BACKGROUND_BLOCKS,
    "hook": HOOK_BLOCKS,
    "structure": STRUCTURE_BLOCKS,
    "style": STYLE_BLOCKS,
    "audience": AUDIENCE_BLOCKS,
    "cast_scale": CAST_SCALE_BLOCKS,
}


# ---------- 1. 每个维度的选项非空 ----------
def test_dimension_options_non_empty():
    for dim in DIMENSION_ORDER:
        assert DIMENSION_OPTIONS[dim], f"{dim} 维度选项为空"
        assert set(DIMENSION_OPTIONS[dim]) == set(DIMENSION_BLOCKS[dim].keys()), (
            f"{dim} DIMENSION_OPTIONS 与积木块 key 不一致"
        )


def test_dimension_labels_complete():
    assert set(DIMENSION_LABELS.keys()) == set(DIMENSION_ORDER)


# ---------- 2. 每块积木 prompt_fragment 非空且长度达标 ----------
@pytest.mark.parametrize("dim", DIMENSION_ORDER)
def test_each_block_fragment_valid(dim):
    blocks = DIMENSION_BLOCKS[dim]
    assert blocks, f"{dim} 没有积木块"
    for key, block in blocks.items():
        frag = block["prompt_fragment"]
        assert isinstance(frag, str) and frag.strip(), f"{dim}/{key} prompt_fragment 为空"
        assert len(frag) >= MIN_FRAGMENT_LEN, (
            f"{dim}/{key} prompt_fragment 过短：{len(frag)} 字 < {MIN_FRAGMENT_LEN}"
        )


def test_all_blocks_have_label():
    for dim, blocks in DIMENSION_BLOCKS.items():
        for key, block in blocks.items():
            assert block.get("label"), f"{dim}/{key} 缺 label"


# ---------- 3. build_context 正确 ----------
def test_build_context_contains_selected_fragments():
    config = {
        "core_genre": "玄幻",
        "background": "宗门林立",
        "hook": "金手指系统",
        "structure": "升级打怪",
        "style": "热血澎湃",
        "audience": "爽文快感",
        "cast_scale": "独角戏",
    }
    ctx = build_context(config)
    # 每个维度都出现在上下文中
    for dim, option in config.items():
        label = DIMENSION_BLOCKS[dim][option]["label"]
        assert f"【{DIMENSION_LABELS[dim]}·{label}】" in ctx, f"{dim} 段缺失"
        assert DIMENSION_BLOCKS[dim][option]["prompt_fragment"][:20] in ctx
    # 顺序符合 DIMENSION_ORDER
    positions = [ctx.index(f"【{DIMENSION_LABELS[dim]}") for dim in DIMENSION_ORDER]
    assert positions == sorted(positions), "写作上下文段落顺序应遵循 DIMENSION_ORDER"


def test_build_context_empty_and_partial():
    assert build_context(None) == ""
    assert build_context({}) == ""
    ctx = build_context({"style": "冷峻写实"})
    assert "【文风基调·冷峻写实】" in ctx
    assert "冷峻" in ctx


def test_build_context_unknown_option_fallback():
    # 未知选项不应崩溃，降级为原文直述
    ctx = build_context({"core_genre": "异世界", "audience": "爽文快感"})
    assert "异世界" in ctx
    assert "【目标受众·爽文快感】" in ctx


# ---------- 4. DEFAULT_RECIPES 覆盖全部核心题材 ----------
def test_default_recipes_cover_all_core_genres():
    assert set(DEFAULT_RECIPES.keys()) == set(CORE_GENRES)


@pytest.mark.parametrize("genre", CORE_GENRES)
def test_default_recipe_values_valid(genre):
    recipe = DEFAULT_RECIPES[genre]
    assert set(recipe.keys()) == set(DIMENSION_ORDER), f"{genre} 配方维度不完整"
    for dim, value in recipe.items():
        assert value in DIMENSION_OPTIONS[dim], f"{genre} 配方 {dim}={value} 非法"


def test_default_recipes_buildable():
    # 任一默认配方都能拼出非空写作上下文
    for genre, recipe in DEFAULT_RECIPES.items():
        ctx = build_context(recipe)
        assert ctx, f"{genre} 默认配方无法生成上下文"
