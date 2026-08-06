# test_arc_summary.py
# -*- coding: utf-8 -*-
"""V3 P3-B 记忆分层：arc 摘要 / 全书摘要合成 / 记忆提取新字段解析 单测。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.generation_service import build_arc_summary, extract_chapter_memory, synthesize_book_summary


def _run(coro):
    return asyncio.run(coro)


class FakeAdapter:
    """假的 LLM adapter：invoke 返回预设内容或抛预设异常。"""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def invoke(self, prompt):
        if self.error:
            raise self.error
        return self.response


def _mk_chapter(num, summary=None):
    """构造带 actual_summary_json 的伪 Chapter。"""
    return SimpleNamespace(
        chapter_num=num,
        actual_summary_json={"summary": summary} if summary else None,
    )


# ============ build_arc_summary ============

class TestBuildArcSummary:
    @patch("app.services.generation_service._make_adapter")
    def test_success_returns_summary_and_chapter_range(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter("这是本 arc 的剧情摘要，涵盖关键事件与伏笔。")
        chapters = [_mk_chapter(1, "第1章记忆"), _mk_chapter(2, "第2章记忆"), _mk_chapter(3, "第3章记忆")]
        result = _run(build_arc_summary(chapters, {"api_key": "test"}, arc_size=15))

        assert result["summary"] == "这是本 arc 的剧情摘要，涵盖关键事件与伏笔。"
        assert result["chapter_range"] == [1, 3]
        mock_make_adapter.assert_called_once_with(temperature=0.2, llm_config={"api_key": "test"})

    @patch("app.services.generation_service.settings.LLM_API_KEY", "")
    def test_no_llm_configured_returns_empty(self):
        chapters = [_mk_chapter(1, "第1章记忆")]
        result = _run(build_arc_summary(chapters, None))
        assert result == {}

    @patch("app.services.generation_service._make_adapter")
    def test_llm_exception_returns_empty(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter(error=RuntimeError("LLM down"))
        chapters = [_mk_chapter(1, "第1章记忆")]
        result = _run(build_arc_summary(chapters, {"api_key": "test"}))
        assert result == {}

    @patch("app.services.generation_service._make_adapter")
    def test_empty_return_returns_empty(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter("   ")
        chapters = [_mk_chapter(1, "第1章记忆")]
        result = _run(build_arc_summary(chapters, {"api_key": "test"}))
        assert result == {}

    @patch("app.services.generation_service._make_adapter")
    def test_no_usable_chapter_memory_returns_empty_without_calling_llm(self, mock_make_adapter):
        # 各章均无可用的 actual_summary_json（None / 空 summary / 非 dict）→ 不调 LLM
        chapters = [
            _mk_chapter(1, None),
            SimpleNamespace(chapter_num=2, actual_summary_json={"summary": "   "}),
            SimpleNamespace(chapter_num=3, actual_summary_json={}),
            SimpleNamespace(chapter_num=4, actual_summary_json=None),
        ]
        result = _run(build_arc_summary(chapters, {"api_key": "test"}))
        assert result == {}
        mock_make_adapter.assert_not_called()

    def test_empty_chapters_returns_empty(self):
        result = _run(build_arc_summary([], {"api_key": "test"}))
        assert result == {}


# ============ synthesize_book_summary ============

class TestSynthesizeBookSummary:
    @patch("app.services.generation_service._make_adapter")
    def test_success_returns_book_summary(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter("全书摘要：人物与主线脉络。")
        arcs = [
            {"arc_index": 0, "chapter_range": [1, 15], "title": "第1-15章", "summary": "arc1 摘要"},
            {"arc_index": 1, "chapter_range": [16, 30], "title": "第16-30章", "summary": "arc2 摘要"},
        ]
        result = _run(synthesize_book_summary(arcs, {"api_key": "test"}))
        assert result == "全书摘要：人物与主线脉络。"

    @patch("app.services.generation_service.settings.LLM_API_KEY", "")
    def test_no_llm_configured_returns_empty(self):
        assert _run(synthesize_book_summary([{"summary": "a"}], None)) == ""

    @patch("app.services.generation_service._make_adapter")
    def test_llm_exception_returns_empty(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter(error=RuntimeError("LLM down"))
        result = _run(synthesize_book_summary([{"summary": "a"}], {"api_key": "test"}))
        assert result == ""

    @patch("app.services.generation_service._make_adapter")
    def test_empty_return_returns_empty(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter("")
        result = _run(synthesize_book_summary([{"summary": "a"}], {"api_key": "test"}))
        assert result == ""

    @patch("app.services.generation_service._make_adapter")
    def test_no_usable_arc_summary_returns_empty_without_calling_llm(self, mock_make_adapter):
        arcs = [
            {},
            {"summary": "   "},
            {"arc_index": 0, "summary": None},
        ]
        result = _run(synthesize_book_summary(arcs, {"api_key": "test"}))
        assert result == ""
        mock_make_adapter.assert_not_called()

    def test_empty_arcs_returns_empty(self):
        assert _run(synthesize_book_summary([], {"api_key": "test"})) == ""


# ============ extract_chapter_memory 新字段解析 ============

class TestExtractChapterMemoryNewFields:
    @patch("app.services.generation_service._make_adapter")
    def test_new_fields_preserved(self, mock_make_adapter):
        raw_json = (
            '{"summary": "摘要", "hook": "钩子", '
            '"foreshadowing_added": [{"name": "铜匣", "note": "说明", "known_by": ["主角"]}], '
            '"foreshadowing_touched": ["旧伏笔A"], '
            '"foreshadowing_recovered": ["旧伏笔B"], '
            '"subplot_advanced": ["商会线"]}'
        )
        mock_make_adapter.return_value = FakeAdapter(raw_json)
        chapter = SimpleNamespace(draft="正文", chapter_num=1)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))

        assert result["foreshadowing_added"] == [{"name": "铜匣", "note": "说明", "known_by": ["主角"]}]
        assert result["foreshadowing_touched"] == ["旧伏笔A"]
        assert result["foreshadowing_recovered"] == ["旧伏笔B"]
        assert result["subplot_advanced"] == ["商会线"]

    @patch("app.services.generation_service._make_adapter")
    def test_missing_new_fields_default_to_empty_lists(self, mock_make_adapter):
        # 旧格式输出（无新字段）→ 解析后补齐空列表，台账合并可直接消费
        mock_make_adapter.return_value = FakeAdapter('{"summary": "摘要", "hook": "h"}')
        chapter = SimpleNamespace(draft="正文", chapter_num=1)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))

        assert result["foreshadowing_touched"] == []
        assert result["foreshadowing_recovered"] == []
        assert result["subplot_advanced"] == []
        assert result["foreshadowing_added"] == []

    @patch("app.services.generation_service._make_adapter")
    def test_foreshadowing_added_non_list_normalized(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter('{"summary": "摘要", "foreshadowing_added": "不是列表"}')
        chapter = SimpleNamespace(draft="正文", chapter_num=1)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))
        assert result["foreshadowing_added"] == []
