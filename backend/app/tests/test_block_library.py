# test_block_library.py
# -*- coding: utf-8 -*-
"""积木库（用户层 7 维）单元测试。"""

import pytest

from app.generator.block_library import (
    AUDIENCE_BLOCKS,
    BACKGROUND_BLOCKS,
    BACKGROUND_SYSTEMS,
    CAST_SCALE_BLOCKS,
    CORE_GENRE_BLOCKS,
    CORE_GENRES,
    DEFAULT_RECIPES,
    DIMENSION_BLOCKS,
    DIMENSION_LABELS,
    DIMENSION_OPTIONS,
    DIMENSION_ORDER,
    GENRE_HARD_BACKGROUND,
    HARD_CONFLICTS,
    HOOK_BLOCKS,
    INTERNAL_FLAVORS,
    SOFT_WARNINGS,
    STRUCTURE_BLOCKS,
    STYLE_BLOCKS,
    build_context,
    check_hard_conflicts,
    check_soft_warnings,
    roll_internal_flavor,
    validate_writing_config,
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


# ---------- 3.6 用户自定义要求（writing_config.custom 5 字段） ----------
def test_build_context_renders_custom_requirements():
    # custom 5 字段有值时拼成【用户自定义要求】段，各字段原文注入
    config = {
        "core_genre": "玄幻",
        "background": "宗门林立",
        "custom": {
            "core_selling_point": "强调金手指的代价与成长",
            "unique_setting": "以炼丹师为唯一修炼体系",
            "character_req": "主角性格坚韧但非全知全能",
            "avoid": "避免主角无脑碾压",
            "free_note": "希望文风带一点幽默",
        },
    }
    ctx = build_context(config)
    assert "【用户自定义要求】" in ctx
    for text in ("核心卖点要求：强调金手指的代价与成长",
                 "独特设定：以炼丹师为唯一修炼体系",
                 "角色要求：主角性格坚韧但非全知全能",
                 "需避免：避免主角无脑碾压",
                 "补充说明：希望文风带一点幽默"):
        assert text in ctx, f"custom 字段未注入上下文：{text}"
    # 自定义要求段应排在最后
    assert ctx.rindex("【用户自定义要求】") > ctx.rindex("【核心题材")


def test_build_context_custom_partial_fields_only_present():
    # 只填部分字段时，仅有值的字段出现
    config = {"core_genre": "都市", "custom": {"avoid": "不写悲剧结局"}}
    ctx = build_context(config)
    assert "【用户自定义要求】" in ctx
    assert "需避免：不写悲剧结局" in ctx
    assert "核心卖点要求" not in ctx
    assert "补充说明" not in ctx


def test_build_context_no_custom_when_absent_or_empty():
    # custom 缺失 / 非 dict / 全为空值时，不出现【用户自定义要求】段
    assert "【用户自定义要求】" not in build_context({"core_genre": "玄幻"})
    assert "【用户自定义要求】" not in build_context({"core_genre": "玄幻", "custom": {}})
    assert "【用户自定义要求】" not in build_context({"core_genre": "玄幻", "custom": None})
    assert "【用户自定义要求】" not in build_context({"core_genre": "玄幻", "custom": {"avoid": "   "}})


# ---------- 3.7 roll_internal_flavor 类型防御 ----------
def test_roll_internal_flavor_non_string_genre_guard():
    # 非字符串 core_genre（缺失 / None / 不可哈希类型）不得抛 TypeError，置空列表
    assert roll_internal_flavor({})["internal_flavor"] == []
    assert roll_internal_flavor({"core_genre": None})["internal_flavor"] == []
    assert roll_internal_flavor({"core_genre": ["玄幻"]})["internal_flavor"] == []
    assert roll_internal_flavor({"core_genre": {"x": 1}})["internal_flavor"] == []


# ---------- 8. 写作配置冲突规则引擎 ----------
def test_rule_data_structures_complete():
    # 规则数据齐全：4 背景系、题材硬禁背景、硬冲突、软警告非空
    assert set(BACKGROUND_SYSTEMS.keys()) == {"古风", "山野", "现代", "未来"}
    assert BACKGROUND_SYSTEMS["山野"]["neutral"] is True
    assert GENRE_HARD_BACKGROUND == {"历史": ["现代", "未来"], "体育": ["古风", "未来"]}
    assert HARD_CONFLICTS and SOFT_WARNINGS
    # 背景系成员都来自 BACKGROUND_BLOCKS，且不重叠
    all_bg = [b for info in BACKGROUND_SYSTEMS.values() for b in info["背景块"]]
    assert len(all_bg) == len(set(all_bg)) == len(BACKGROUND_BLOCKS), "背景块未全覆盖或不重复"


# ---------- 8.1 硬冲突 ----------
def test_hard_conflict_background_cross_system():
    # 背景跨系（同维多选）：古风 + 未来 不能并存
    hard = check_hard_conflicts({"background": ["宗门林立", "末世废土"]})
    assert hard, "背景跨系（古风+未来）应报硬冲突"
    assert any("背景跨系" in m for m in hard)


def test_hard_conflict_background_neutral_pairs_any_system():
    # 山野中性系不与任何系冲突（山野 + 未来 不报）
    assert check_hard_conflicts({"background": ["山野灵异", "星际远征"]}) == []
    assert check_hard_conflicts({"background": ["山野灵异", "都市霓虹"]}) == []


def test_hard_conflict_background_string_single_no_cross():
    # 背景传字符串（单选）永不触发跨系
    assert check_hard_conflicts({"background": "宗门林立"}) == []


def test_hard_conflict_genre_history_x_modern():
    # 历史 × 现代背景（都市霓虹）
    hard = check_hard_conflicts({"core_genre": "历史", "background": "都市霓虹"})
    assert hard
    assert any("历史" in m and "都市霓虹" in m for m in hard)


def test_hard_conflict_genre_history_x_future():
    # 历史 × 未来背景（星际远征）
    hard = check_hard_conflicts({"core_genre": "历史", "background": "星际远征"})
    assert hard and any("历史" in m and "星际远征" in m for m in hard)


def test_hard_conflict_genre_sports_x_ancient():
    # 体育 × 古风背景（宗门林立）
    hard = check_hard_conflicts({"core_genre": "体育", "background": "宗门林立"})
    assert hard and any("体育" in m and "宗门林立" in m for m in hard)


def test_hard_conflict_genre_mixed_background_partial():
    # 多选背景中只要含一个禁系即触发（历史 + 古风 + 未来）
    hard = check_hard_conflicts({"core_genre": "历史", "background": ["王朝庙堂", "星际远征"]})
    assert hard and any("星际远征" in m for m in hard)


def test_hard_conflict_cast_x_structure_lean_x_ensemble():
    # 精简×群像：独角戏（精简卡司）× 群像交织（多线群像结构）
    hard = check_hard_conflicts({"cast_scale": "独角戏", "structure": "群像交织"})
    assert hard
    assert any("独角戏" in m and "群像交织" in m for m in hard)


def test_hard_conflict_hook_invincible_x_face_slap():
    # 无敌流×打脸：金手指系统 + 打脸爽感
    hard = check_hard_conflicts({"hook": ["金手指系统", "打脸爽感"]})
    assert hard
    assert any("金手指系统" in m and "打脸爽感" in m for m in hard)


def test_hard_conflict_internal_flavor_soft_x_strong():
    # 娇软×女强：言情内部风味 娇软治愈 + 女强飒爽
    hard = check_hard_conflicts(
        {"core_genre": "言情", "internal_flavor": ["娇软治愈", "女强飒爽"]}
    )
    assert hard
    assert any("娇软治愈" in m and "女强飒爽" in m for m in hard)


def test_hard_conflict_missing_dim_no_conflict():
    # 缺失维度视为未选、不报冲突
    assert check_hard_conflicts({}) == []
    assert check_hard_conflicts(None) == []
    assert check_hard_conflicts({"core_genre": "历史"}) == []
    assert check_hard_conflicts({"background": "都市霓虹"}) == []


def test_hard_conflict_unknown_values_no_crash():
    # 未知取值不崩溃、不误报
    assert check_hard_conflicts({"background": ["未知背景"], "cast_scale": "未知规模"}) == []
    assert check_hard_conflicts({"core_genre": "未知题材", "background": "宗门林立"}) == []


# ---------- 8.2 软警告 ----------
def test_soft_warning_genre_x_background_fusion():
    # 罕见融合：仙侠 × 末世废土
    soft = check_soft_warnings({"core_genre": "仙侠", "background": "末世废土"})
    assert soft
    assert any("罕见融合" in m and "仙侠" in m and "末世废土" in m for m in soft)
    # 罕见融合是软警告而非硬冲突
    assert check_hard_conflicts({"core_genre": "仙侠", "background": "末世废土"}) == []


def test_soft_warning_style_x_audience_tension():
    # 文风×受众张力：冷峻写实 × 轻松解压
    soft = check_soft_warnings({"style": "冷峻写实", "audience": "轻松解压"})
    assert soft
    assert any("冷峻写实" in m and "轻松解压" in m for m in soft)


def test_soft_warning_hook_x_genre_mismatch():
    # 卖点错位：情感拉扯 × 军事
    soft = check_soft_warnings({"core_genre": "军事", "hook": ["情感拉扯"]})
    assert soft and any("卖点错位" in m for m in soft)


def test_soft_warning_structure_x_background():
    # 结构×背景：日常流 × 星际远征
    soft = check_soft_warnings({"structure": "日常流", "background": "星际远征"})
    assert soft and any("结构与背景" in m for m in soft)


def test_soft_warning_reborn_x_transmigrate():
    # 重生×穿越冗余
    soft = check_soft_warnings({"hook": ["重生逆袭", "穿越异世"]})
    assert soft and any("重生" in m and "穿越" in m for m in soft)


def test_soft_warning_plot_vs_setting():
    # 剧情走向×设定：剧情写现代都市，背景却是星际远征
    soft = check_soft_warnings(
        {"background": "星际远征", "plot_direction": "主角在现代都市的职场一路逆袭"}
    )
    assert soft and any("剧情走向" in m and "星际远征" in m for m in soft)


def test_soft_warning_plot_matches_background_no_warning():
    # 剧情走向与背景同系不报
    assert check_soft_warnings(
        {"background": "都市霓虹", "plot_direction": "主角在现代都市的职场一路逆袭"}
    ) == []
    # 剧情走向遇上中性背景（山野）也不报
    assert check_soft_warnings(
        {"background": "山野灵异", "plot_direction": "主角在现代都市的职场一路逆袭"}
    ) == []


def test_soft_warning_missing_plot_or_background_no_warning():
    # 剧情走向未填 / 背景未选 → 不报剧情走向冲突
    assert check_soft_warnings({"background": "星际远征"}) == []
    assert check_soft_warnings({"plot_direction": "主角在现代都市打拼"}) == []
    assert check_soft_warnings({}) == []
    assert check_soft_warnings(None) == []


# ---------- 8.3 validate_writing_config 汇总 ----------
def test_validate_writing_config_shape():
    res = validate_writing_config({"background": ["宗门林立", "末世废土"]})
    assert set(res.keys()) == {"hard", "soft", "valid"}
    assert isinstance(res["hard"], list) and isinstance(res["soft"], list)
    assert res["valid"] is False


def test_validate_clean_config_no_conflict():
    # 无冲突配置：硬软均空、valid=True
    res = validate_writing_config(DEFAULT_RECIPES["玄幻"])
    assert res["hard"] == [] and res["soft"] == []
    assert res["valid"] is True


def test_validate_mixed_hard_and_soft():
    # 硬冲突 + 软警告并存时：valid=False，且两类都返回
    res = validate_writing_config(
        {"core_genre": "历史", "background": "都市霓虹", "style": "冷峻写实", "audience": "轻松解压"}
    )
    assert res["valid"] is False
    assert res["hard"]
    assert res["soft"]


@pytest.mark.parametrize("genre", CORE_GENRES)
def test_all_default_recipes_validate_clean(genre):
    # 全部默认配方不得触发任何硬冲突或软警告（保证既有创建流程无冲突行为不变）
    res = validate_writing_config(DEFAULT_RECIPES[genre])
    assert res["valid"] is True, f"{genre} 默认配方不应有硬冲突：{res['hard']}"
    assert res["soft"] == [], f"{genre} 默认配方不应有软警告：{res['soft']}"
