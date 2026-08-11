# test_asset_versions.py
# -*- coding: utf-8 -*-
"""架构/目录 优化重新生成 + 版本历史回滚 单元测试。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.services.generation_service import generate_architecture, generate_directory


def _run(coro):
    return asyncio.run(coro)


class CapturingAdapter:
    """记录每次 invoke 的 prompt，返回固定非空响应。"""

    def __init__(self, response="已生成内容"):
        self.response = response
        self.prompts = []

    async def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.response


def _project(**overrides):
    base = dict(
        topic="测试主题",
        genre="玄幻",
        num_chapters=3,
        word_number=1500,
        writing_config={"structure": "日常流", "core_genre": "玄幻"},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


_LLM = {"api_key": "test-key"}

_DIRECTORY = "第1章 - 开篇\n本章简述：开场。\n\n第2章 - 发展\n本章简述：推进。\n\n第3章 - 收束\n本章简述：收尾。"

_CURRENT = "【核心种子】\n现有设定全文"


class TestCurrentContentInjection:
    """current_content 注入后 prompt 含「参考当前版本」段；缺省不含。"""

    @patch("app.services.generation_service._make_adapter")
    def test_architecture_injects_current_content(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        _run(generate_architecture(_project(), current_content=_CURRENT, llm_config=_LLM))
        assert len(adapter.prompts) >= 4
        for p in adapter.prompts[:4]:
            assert "参考当前版本" in p
            assert _CURRENT in p

    @patch("app.services.generation_service._make_adapter")
    def test_architecture_without_current_content_no_section(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        _run(generate_architecture(_project(), llm_config=_LLM))
        for p in adapter.prompts[:4]:
            assert "参考当前版本" not in p

    @patch("app.services.generation_service._make_adapter")
    def test_directory_injects_current_content(self, mock_adapter):
        adapter = CapturingAdapter(_DIRECTORY)
        mock_adapter.return_value = adapter
        _run(generate_directory(_project(), architecture_text="架构", current_content=_CURRENT, llm_config=_LLM))
        prompt = adapter.prompts[0]
        assert "参考当前版本" in prompt
        assert _CURRENT in prompt

    @patch("app.services.generation_service._make_adapter")
    def test_directory_without_current_content_no_section(self, mock_adapter):
        adapter = CapturingAdapter(_DIRECTORY)
        mock_adapter.return_value = adapter
        _run(generate_directory(_project(), architecture_text="架构", llm_config=_LLM))
        assert "参考当前版本" not in adapter.prompts[0]


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class FakeDB:
    """按查询顺序返回预设行的最小 AsyncSession 替身。

    results: 每次 execute 依次 pop 返回；耗尽后返回 None。
    versions: record_asset_version 写入的行参数（供断言）。
    """

    def __init__(self, results=None):
        self.results = list(results or [])
        self.versions = []
        self.committed = False

    async def execute(self, stmt):
        return _FakeResult(self.results.pop(0) if self.results else None)

    def add(self, obj):
        # brief 原文为 pass，导致 db.versions 永远为空、所有断言失败；
        # 按 docstring 语义（versions 供断言 record_asset_version 写入的行参数）捕获 AssetVersion。
        if hasattr(obj, "trigger_type"):
            self.versions.append({
                "project_id": obj.project_id,
                "asset_type": obj.asset_type,
                "content_text": obj.content_text,
                "version": obj.version,
                "trigger_type": obj.trigger_type,
                "guidance": obj.guidance,
                "created_by": obj.created_by,
            })

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = "test-id"
        if getattr(obj, "version", None) is None:
            obj.version = 1
        if getattr(obj, "created_at", None) is None:
            obj.created_at = "2026-08-11T00:00:00+00:00"
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = "2026-08-11T00:00:00+00:00"


class TestSaveAssetWritesVersion:
    """_save_asset 对 architecture/directory 写历史行且 version 递增；其他类型不写。"""

    def test_architecture_writes_version_row(self):
        from app.services.task_service import _save_asset

        existing = SimpleNamespace(content_text="旧", version=2)
        db = FakeDB(results=[existing])
        _run(_save_asset(db, "p1", "architecture", "新内容", trigger_type="generate", guidance="提示词"))
        assert existing.content_text == "新内容"
        assert existing.version == 3
        assert db.versions == [{
            "project_id": "p1", "asset_type": "architecture", "content_text": "新内容",
            "version": 3, "trigger_type": "generate", "guidance": "提示词", "created_by": None,
        }]

    def test_directory_writes_manual_version_row(self):
        from app.services.task_service import _save_asset

        existing = SimpleNamespace(content_text="旧", version=1)
        db = FakeDB(results=[existing])
        _run(_save_asset(db, "p1", "directory", "新目录", trigger_type="manual", guidance=None))
        assert db.versions[0]["trigger_type"] == "manual"

    def test_world_state_does_not_write_version_row(self):
        from app.services.task_service import _save_asset

        existing = SimpleNamespace(content_text="{}", version=5)
        db = FakeDB(results=[existing])
        _run(_save_asset(db, "p1", "world_state", "{}", trigger_type="generate"))
        assert db.versions == []
        assert existing.version == 6


class TestRollbackAsset:
    """rollback_asset 写回内容、version 续 +1、写 rollback 行；目标不存在返回 False。"""

    def test_rollback_success(self):
        from app.services.task_service import rollback_asset

        target = SimpleNamespace(content_text="v2 的内容")
        current = SimpleNamespace(content_text="v3 的内容", version=3)
        db = FakeDB(results=[target, current])
        ok = _run(rollback_asset(db, "p1", "architecture", 2, user_id="u1"))
        assert ok is True
        assert current.content_text == "v2 的内容"
        assert current.version == 4
        assert db.versions == [{
            "project_id": "p1", "asset_type": "architecture", "content_text": "v2 的内容",
            "version": 4, "trigger_type": "rollback", "guidance": "回滚至 v2", "created_by": "u1",
        }]

    def test_rollback_target_missing_returns_false(self):
        from app.services.task_service import rollback_asset

        db = FakeDB(results=[None])
        ok = _run(rollback_asset(db, "p1", "architecture", 99))
        assert ok is False
        assert db.versions == []
