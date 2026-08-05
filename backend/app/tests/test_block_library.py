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
    INTERNAL_FLAVORS,
    STRUCTURE_BLOCKS,
    STYLE_BLOCKS,
    build_context,
    roll_internal_flavor,
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


# ---------- 3.5 多选维度（background / hook）数组值 ----------
def test_build_context_background_array_injects_each_fragment():
    # 背景为数组时，逐项注入各选项的 prompt_fragment 核心内容
    config = {
        "core_genre": "玄幻",
        "background": ["宗门林立", "大陆争霸"],
        "hook": ["金手指系统"],
    }
    ctx = build_context(config)
    assert "【故事背景】" in ctx
    for key in ("宗门林立", "大陆争霸"):
        assert key in ctx
        frag = BACKGROUND_BLOCKS[key]["prompt_fragment"]
        assert frag[:20] in ctx, f"{key} 的 prompt_fragment 未注入上下文"


def test_build_context_hook_array_injects_each_fragment():
    # 卖点为数组时，逐项注入各选项的 prompt_fragment 核心内容
    config = {
        "core_genre": "都市",
        "background": "都市霓虹",
        "hook": ["打脸爽感", "扮猪吃虎"],
    }
    ctx = build_context(config)
    assert "【核心卖点】" in ctx
    for key in ("打脸爽感", "扮猪吃虎"):
        assert key in ctx
        frag = HOOK_BLOCKS[key]["prompt_fragment"]
        assert frag[:20] in ctx, f"{key} 的 prompt_fragment 未注入上下文"
    # 背景仍传字符串时走原单选逻辑
    assert "【故事背景·都市霓虹】" in ctx


def test_build_context_array_with_unknown_item_fallback():
    # 数组中混入未知项（新选项/自由文本）不崩溃，且未知项降级为原文直述
    config = {
        "core_genre": "玄幻",
        "background": ["宗门林立", "洪荒", "西游"],
        "hook": ["金手指系统", "时间循环"],
    }
    ctx = build_context(config)
    assert "【故事背景】" in ctx
    assert "宗门林立" in ctx
    for unknown in ("洪荒", "西游", "时间循环"):
        assert unknown in ctx, f"未知项 {unknown} 应降级原文直述"
    assert HOOK_BLOCKS["金手指系统"]["prompt_fragment"][:20] in ctx


def test_build_context_array_order_follows_dimension_order():
    # 多选数组段仍遵循 DIMENSION_ORDER：背景在卖点之前
    config = {
        "core_genre": "玄幻",
        "background": ["宗门林立"],
        "hook": ["金手指系统"],
    }
    ctx = build_context(config)
    assert ctx.index("【故事背景") < ctx.index("【核心卖点")


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


# ---------- 5. 内部细粒度风味层 ----------
MIN_FLAVOR_FRAGMENT_LEN = 40


def test_internal_flavors_cover_all_core_genres():
    # 每个核心题材都有一组内部风味
    assert set(INTERNAL_FLAVORS.keys()) == set(CORE_GENRES)


@pytest.mark.parametrize("genre", CORE_GENRES)
def test_internal_flavor_group_size_in_range(genre):
    # 每组 5-8 个细粒度风味块
    n = len(INTERNAL_FLAVORS[genre])
    assert 5 <= n <= 8, f"{genre} 风味数量 {n} 不在 5-8 范围"


@pytest.mark.parametrize("genre", CORE_GENRES)
def test_internal_flavor_blocks_valid(genre):
    # 每块有 label + 足够具体的风味文本（2-3 句，非干词条）
    for key, block in INTERNAL_FLAVORS[genre].items():
        assert block.get("label"), f"{genre}/{key} 缺 label"
        frag = block["prompt_fragment"]
        assert isinstance(frag, str) and frag.strip(), f"{genre}/{key} 风味文本为空"
        assert len(frag) >= MIN_FLAVOR_FRAGMENT_LEN, (
            f"{genre}/{key} 风味文本过短：{len(frag)} 字 < {MIN_FLAVOR_FRAGMENT_LEN}"
        )


def test_roll_internal_flavor_writes_valid_result():
    # 返回合法结果、不越界：1-3 个、属于该题材、不重复、原地写回
    config = {"core_genre": "玄幻"}
    cfg = roll_internal_flavor(config)
    assert cfg is config, "roll_internal_flavor 应原地写回 config"
    keys = set(INTERNAL_FLAVORS["玄幻"].keys())
    picked = cfg["internal_flavor"]
    assert isinstance(picked, list)
    assert 1 <= len(picked) <= 3, f"单次应掷出 1-3 个风味，实际 {len(picked)}"
    assert set(picked) <= keys, "风味越界（不属于该题材）"
    assert len(set(picked)) == len(picked), "风味不应重复"


@pytest.mark.parametrize("genre", CORE_GENRES)
def test_roll_internal_flavor_respects_genre(genre):
    # 任意核心题材掷出的风味都属于该题材自己的组
    for _ in range(20):
        cfg = roll_internal_flavor({"core_genre": genre})
        keys = set(INTERNAL_FLAVORS[genre].keys())
        assert set(cfg["internal_flavor"]) <= keys, f"{genre} 风味越界"


def test_roll_internal_flavor_missing_or_unknown_genre():
    # 缺失题材 / 未知题材 → 空列表，不崩溃
    assert roll_internal_flavor({})["internal_flavor"] == []
    assert roll_internal_flavor({"core_genre": "不存在的题材"})["internal_flavor"] == []
    assert roll_internal_flavor(None) == {}


def test_roll_internal_flavor_many_rolls_stay_in_bounds():
    # 大量掷风味始终合法、不越界
    for _ in range(200):
        cfg = roll_internal_flavor({"core_genre": "都市"})
        keys = set(INTERNAL_FLAVORS["都市"].keys())
        assert set(cfg["internal_flavor"]) <= keys
        assert 1 <= len(cfg["internal_flavor"]) <= 3


def test_build_context_contains_internal_flavor():
    config = {"core_genre": "玄幻", "internal_flavor": ["洪荒色彩"]}
    ctx = build_context(config)
    assert "【内部风味】" in ctx
    assert "洪荒色彩" in ctx
    frag = INTERNAL_FLAVORS["玄幻"]["洪荒色彩"]["prompt_fragment"]
    assert frag[:20] in ctx, "风味 prompt_fragment 应注入上下文"


def test_build_context_multiple_internal_flavors():
    config = {"core_genre": "玄幻", "internal_flavor": ["洪荒色彩", "高武"]}
    ctx = build_context(config)
    for name in ("洪荒色彩", "高武"):
        assert name in ctx
    # 两个风味都在同一段内
    assert ctx.count("【内部风味】") == 1


def test_build_context_internal_flavor_after_genre():
    # 内部风味紧跟核心题材段之后（题材的细化）
    config = {"core_genre": "玄幻", "internal_flavor": ["高武"]}
    ctx = build_context(config)
    assert ctx.index("【核心题材") < ctx.index("【内部风味】")


def test_build_context_no_internal_flavor_when_absent():
    # 未掷风味时上下文不出现内部风味段，且不影响原 7 维拼接
    ctx = build_context({"core_genre": "玄幻"})
    assert "【内部风味】" not in ctx
    assert "【核心题材·玄幻】" in ctx


def test_build_context_unknown_internal_flavor_fallback():
    # 未知风味（前端/上游新传值）降级原文直述，不崩溃
    ctx = build_context({"core_genre": "玄幻", "internal_flavor": ["未来新风味"]})
    assert "【内部风味】" in ctx
    assert "未来新风味" in ctx


def test_build_context_default_recipe_with_rolled_flavor():
    # 默认配方 + 掷出的风味能拼出包含风味的完整上下文
    for genre, recipe in DEFAULT_RECIPES.items():
        cfg = dict(recipe)
        roll_internal_flavor(cfg)
        ctx = build_context(cfg)
        assert ctx, f"{genre} 默认配方+风味无法生成上下文"
        if cfg["internal_flavor"]:
            assert "【内部风味】" in ctx, f"{genre} 上下文缺失内部风味段"
