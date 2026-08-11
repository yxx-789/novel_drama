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
