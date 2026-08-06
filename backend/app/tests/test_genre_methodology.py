# test_genre_methodology.py
# -*- coding: utf-8 -*-
"""V3 P3-A 题材方法论：参数表完整性 / 渲染 / 未知题材回退 单元测试。"""

from app.generator.genre_methodology import (
    DEFAULT_METHODOLOGY,
    GENRE_METHODOLOGY,
    HOOK_FOUR_BREAKS,
    _render_genre_methodology,
    get_genre_methodology,
)


def test_hook_four_breaks_has_exactly_four():
    assert HOOK_FOUR_BREAKS == ["决定", "发现", "误判", "代价"]
    assert len(HOOK_FOUR_BREAKS) == 4


def test_unknown_genre_returns_default():
    assert get_genre_methodology("不存在的题材") is DEFAULT_METHODOLOGY
    assert get_genre_methodology("") is DEFAULT_METHODOLOGY
    assert get_genre_methodology(None) is DEFAULT_METHODOLOGY
    assert get_genre_methodology(123) is DEFAULT_METHODOLOGY


def test_default_methodology_complete():
    assert DEFAULT_METHODOLOGY["conflict_driver"]
    assert len(DEFAULT_METHODOLOGY["foreshadowing_intervals"]) == 3
    assert len(DEFAULT_METHODOLOGY["touch_every"]) == 2
    assert isinstance(DEFAULT_METHODOLOGY["hook_preference"], list)


def test_covers_all_core_genres():
    """12 个核心题材（block_library 定义）全覆盖 + 种田兼容键。"""
    from app.generator.block_library import CORE_GENRE_BLOCKS
    for genre in CORE_GENRE_BLOCKS:
        assert genre in GENRE_METHODOLOGY, f"缺失题材方法论: {genre}"
    assert "种田" in GENRE_METHODOLOGY


def _assert_entry_complete(genre, m):
    assert isinstance(m, dict), genre
    assert m["conflict_driver"] and len(m["conflict_driver"]) >= 10, genre
    intervals = m["foreshadowing_intervals"]
    assert set(intervals.keys()) == {"short", "mid", "long"}, genre
    for k in ("short", "mid", "long"):
        lo, hi = intervals[k]
        assert isinstance(lo, int) and isinstance(hi, int), genre
        assert 0 < lo <= hi, genre
    assert len(m["touch_every"]) == 2 and m["touch_every"][0] <= m["touch_every"][1], genre
    assert isinstance(m["recovery_audit"], bool), genre
    assert m["hook_preference"], genre
    # hook 偏好必须是四断法子集
    assert set(m["hook_preference"]) <= set(HOOK_FOUR_BREAKS), genre
    assert m["opening_arc"] and len(m["opening_arc"]) >= 10, genre


def test_all_entries_complete_and_orthogonal():
    for genre, m in GENRE_METHODOLOGY.items():
        _assert_entry_complete(genre, m)


def test_render_contains_key_parameters():
    text = _render_genre_methodology("悬疑")
    assert "伏笔回收间距" in text
    assert "冲突驱动" in text
    assert "爽点节奏" in text
    assert "章末钩子偏好" in text
    assert "短线" in text and "长线" in text
    # 悬疑偏好 发现/误判 应出现在渲染里
    assert "发现" in text and "误判" in text
    # 渲染片段足够长，有语义内容
    assert len(text) >= 60


def test_render_for_unknown_genre_falls_back():
    text = _render_genre_methodology("不存在的题材")
    assert "伏笔回收间距" in text
    assert len(text) >= 60


def test_render_for_all_core_genres_nonempty():
    from app.generator.block_library import CORE_GENRE_BLOCKS
    for genre in CORE_GENRE_BLOCKS:
        text = _render_genre_methodology(genre)
        assert text and len(text) >= 50, genre
