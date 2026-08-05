# test_memory.py
# -*- coding: utf-8 -*-
"""动态前章窗口（章节结尾衔接上下文）单元测试。"""

from app.services.generation_service import _chapter_excerpt


def test_short_chapter_returns_full_draft():
    # 长度 <= 800 时返回全文
    draft = "短" * 500
    assert _chapter_excerpt(draft) == draft


def test_chapter_at_lower_bound_returns_full_draft():
    # 恰好 800 字时也返回全文
    draft = "短" * 800
    assert _chapter_excerpt(draft) == draft


def test_long_chapter_returns_20_percent_window():
    # 5000 * 20% = 1000，落在 [800, 2000] 区间内
    draft = "长" * 5000
    result = _chapter_excerpt(draft)
    assert len(result) == 1000
    assert result == draft[-1000:]


def test_long_chapter_window_floor_at_800():
    # 4000 * 20% = 800，恰好等于下限
    draft = "长" * 4000
    result = _chapter_excerpt(draft)
    assert len(result) == 800
    assert result == draft[-800:]


def test_long_chapter_window_capped_at_2000():
    # 15000 * 20% = 3000 > 2000，封顶 2000
    draft = "长" * 15000
    result = _chapter_excerpt(draft)
    assert len(result) == 2000
    assert result == draft[-2000:]


def test_empty_input_returns_empty_string():
    assert _chapter_excerpt(None) == ""
    assert _chapter_excerpt("") == ""
