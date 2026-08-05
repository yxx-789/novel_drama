# test_chapter_memory.py
# -*- coding: utf-8 -*-
"""结构化章节记忆提取 + 管线接入单元测试。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.generation_service import extract_chapter_memory
from app.services.task_service import _previous_chapter_summary, run_batch_chapters_task


def _run(coro):
    return asyncio.run(coro)


class FakeAdapter:
    """假的 LLM adapter，invoke 返回预设内容或抛出预设异常。"""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error

    async def invoke(self, prompt):
        if self.error:
            raise self.error
        return self.response


def _fake_chapter(draft="", chapter_num=1, actual_summary_json=None, outline=""):
    return SimpleNamespace(
        draft=draft,
        chapter_num=chapter_num,
        actual_summary_json=actual_summary_json,
        outline=outline,
    )


class TestExtractChapterMemory:
    """extract_chapter_memory mock 测试。"""

    @patch("app.services.generation_service._make_adapter")
    def test_success_returns_structured_memory(self, mock_make_adapter):
        raw_json = (
            '{"summary": "实际摘要", "hook": "悬念", '
            '"characters": ["张三"], '
            '"relations_changed": {"张三-李四": "关系变化"}, '
            '"foreshadowing_added": [{"name": "伏笔", "note": "说明"}], '
            '"connects_to": "续接点"}'
        )
        mock_make_adapter.return_value = FakeAdapter(raw_json)
        chapter = _fake_chapter(draft="正文" * 200)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))

        assert result["summary"] == "实际摘要"
        assert result["hook"] == "悬念"
        assert result["characters"] == ["张三"]
        assert result["relations_changed"] == {"张三-李四": "关系变化"}
        assert result["foreshadowing_added"] == [{"name": "伏笔", "note": "说明"}]
        assert result["connects_to"] == "续接点"
        mock_make_adapter.assert_called_once_with(temperature=0.2, llm_config={"api_key": "test"})

    @patch("app.services.generation_service._make_adapter")
    def test_markdown_code_block_parsed(self, mock_make_adapter):
        raw_json = '```json\n{"summary": "代码块摘要", "hook": "h"}\n```'
        mock_make_adapter.return_value = FakeAdapter(raw_json)
        chapter = _fake_chapter(draft="正文" * 100)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))
        assert result["summary"] == "代码块摘要"

    @patch("app.services.generation_service._make_adapter")
    def test_invalid_json_falls_back_to_first_300_chars(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter("这不是 JSON")
        draft = "字" * 500
        chapter = _fake_chapter(draft=draft)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))
        assert result == {"summary": draft[:300]}

    @patch("app.services.generation_service._make_adapter")
    def test_llm_exception_falls_back(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter(error=RuntimeError("LLM down"))
        draft = "文" * 400
        chapter = _fake_chapter(draft=draft)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))
        assert result == {"summary": draft[:300]}

    @patch("app.services.generation_service._make_adapter")
    def test_missing_summary_filled_with_fallback(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter('{"hook": "只有钩子"}')
        draft = "字" * 300
        chapter = _fake_chapter(draft=draft)
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))
        assert result["summary"] == draft[:300]
        assert result["hook"] == "只有钩子"

    @patch("app.services.generation_service._make_adapter")
    def test_empty_draft_returns_empty_dict_without_calling_llm(self, mock_make_adapter):
        chapter = _fake_chapter(draft="")
        result = _run(extract_chapter_memory(None, chapter, {"api_key": "test"}))
        assert result == {}
        mock_make_adapter.assert_not_called()

    @patch("app.services.generation_service.settings.LLM_API_KEY", "")
    def test_llm_not_configured_returns_fallback_summary(self):
        draft = "字" * 300
        chapter = _fake_chapter(draft=draft)
        result = _run(extract_chapter_memory(None, chapter, None))
        assert result == {"summary": draft[:300]}


class TestPreviousChapterSummary:
    """管线逻辑：前章 actual_summary 优先于 outline。"""

    def test_actual_summary_preferred_over_outline(self):
        prev = _fake_chapter(
            actual_summary_json={"summary": "实际发生的事情摘要", "hook": "悬念"},
            outline="计划中的摘要",
        )
        assert _previous_chapter_summary(prev) == "实际发生的事情摘要"

    def test_actual_summary_missing_falls_back_to_outline(self):
        prev = _fake_chapter(actual_summary_json={"hook": "只有钩子"}, outline="计划中的摘要")
        assert _previous_chapter_summary(prev) == "计划中的摘要"

    def test_actual_summary_empty_string_falls_back_to_outline(self):
        prev = _fake_chapter(actual_summary_json={"summary": "   "}, outline="计划中的摘要")
        assert _previous_chapter_summary(prev) == "计划中的摘要"

    def test_no_actual_summary_uses_outline(self):
        prev = _fake_chapter(actual_summary_json=None, outline="计划中的摘要")
        assert _previous_chapter_summary(prev) == "计划中的摘要"

    def test_no_actual_summary_no_outline_returns_empty(self):
        prev = _fake_chapter(actual_summary_json=None, outline="")
        assert _previous_chapter_summary(prev) == ""

    def test_none_prev_returns_empty(self):
        assert _previous_chapter_summary(None) == ""


# ============ 批量管线接入（wiring）测试 ============

class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResultAll:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _FakeScalars(self._rows)


class _FakeResultOne:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeDB:
    """模拟 AsyncSession：仅支持 run_batch_chapters_task 用到的两条 Chapter 查询。"""

    def __init__(self, chapters):
        self.chapters = chapters
        self.commit_count = 0

    async def commit(self):
        self.commit_count += 1

    async def execute(self, query):
        compiled = query.compile()
        sql = str(compiled)
        if "chapter_num =" in sql:
            # 前章查询：WHERE chapter_num = :n
            key = next(k for k in compiled.params if k.startswith("chapter_num"))
            num = compiled.params[key]
            prev = next((c for c in self.chapters if c.chapter_num == num), None)
            return _FakeResultOne(prev)
        # 列表查询：WHERE project_id = ... ORDER BY chapter_num
        return _FakeResultAll(self.chapters)


class _FakeSessionFactory:
    """模拟 AsyncSessionLocal，`async with` 时产出 FakeDB。"""

    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        return False


def _mk_chapter(chapter_num, outline="", actual_summary_json=None):
    return SimpleNamespace(
        chapter_num=chapter_num,
        outline=outline,
        actual_summary_json=actual_summary_json,
        draft=None,
        status="pending",
        title=f"第{chapter_num}章",
    )


def _patch_batch_pipeline(fake_db, fake_generate_draft, fake_extract_memory):
    """对 run_batch_chapters_task 的依赖做全套 mock。"""
    fake_task = SimpleNamespace(project_id="00000000-0000-0000-0000-000000000001")
    fake_project = SimpleNamespace(
        owner_id="owner-1", genre="", num_chapters=2,
        word_number=2000, topic="", writing_config=None,
    )
    return patch.multiple(
        "app.services.task_service",
        AsyncSessionLocal=_FakeSessionFactory(fake_db),
        get_task_by_id=AsyncMock(return_value=fake_task),
        update_task_status=AsyncMock(),
        get_project_by_id=AsyncMock(return_value=fake_project),
        resolve_llm_config=AsyncMock(return_value={"api_key": "test"}),
        _get_asset_text=AsyncMock(side_effect=lambda db, pid, t: {
            "architecture": "架构文本",
            "directory": "第1章 - 开局\n第2章 - 发展",
            "characters": "角色状态文本",
            "world_state": None,
        }.get(t)),
        generate_chapter_draft=fake_generate_draft,
        extract_chapter_memory=fake_extract_memory,
        extract_world_state_delta=AsyncMock(return_value={"no_changes": True}),
        build_state_summary=AsyncMock(return_value=""),
        check_chapter_consistency=AsyncMock(return_value="CHECK: CONSISTENT"),
        update_character_state=AsyncMock(return_value="新角色状态"),
        _save_asset=AsyncMock(),
    )


class TestBatchPipelineWiring:
    """管线接入：草稿生成后提取记忆、下一章 actual_summary 优先于 outline。"""

    def test_batch_stores_memory_and_uses_actual_summary_for_next_chapter(self):
        ch1 = _mk_chapter(1, outline="第一章大纲")
        ch2 = _mk_chapter(2, outline="第二章大纲")
        chapters = [ch1, ch2]
        fake_db = _FakeDB(chapters)
        calls = []

        async def fake_generate_draft(project, **kwargs):
            calls.append(kwargs)
            return f"第{kwargs['chapter_num']}章草稿"

        async def fake_extract_memory(db, chapter, llm_config):
            return {
                "summary": f"第{chapter.chapter_num}章记忆摘要",
                "hook": "悬念",
                "characters": [],
                "relations_changed": {},
                "foreshadowing_added": [],
                "connects_to": "",
            }

        with _patch_batch_pipeline(fake_db, fake_generate_draft, fake_extract_memory):
            _run(run_batch_chapters_task(uuid.uuid4()))

        # 每章草稿生成后都存入了结构化记忆
        assert ch1.actual_summary_json["summary"] == "第1章记忆摘要"
        assert ch2.actual_summary_json["summary"] == "第2章记忆摘要"
        # 第2章生成时前一章概要用 actual_summary（而非 outline "第一章大纲"）
        assert calls[0]["previous_chapter_summary"] == ""
        assert calls[1]["previous_chapter_summary"] == "第1章记忆摘要"

    def test_batch_falls_back_to_outline_when_no_actual_summary(self):
        """旧项目无 actual_summary_json 时，回退到 prev.outline，保持既有生成行为。"""
        ch1 = _mk_chapter(1, outline="第一章大纲")
        ch2 = _mk_chapter(2, outline="第二章大纲")
        chapters = [ch1, ch2]
        fake_db = _FakeDB(chapters)
        calls = []

        async def fake_generate_draft(project, **kwargs):
            calls.append(kwargs)
            return "draft"

        async def fake_extract_memory(db, chapter, llm_config):
            return {}  # 提取失败 → 空 dict，不写入 actual_summary_json

        with _patch_batch_pipeline(fake_db, fake_generate_draft, fake_extract_memory):
            _run(run_batch_chapters_task(uuid.uuid4()))

        assert ch1.actual_summary_json is None
        assert ch2.actual_summary_json is None
        assert calls[1]["previous_chapter_summary"] == "第一章大纲"
