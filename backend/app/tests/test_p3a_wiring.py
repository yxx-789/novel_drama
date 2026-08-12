# test_p3a_wiring.py
# -*- coding: utf-8 -*-
"""V3 P3-A 接线：structure 分片 / 题材方法论 / 钩子偏好注入 + 记忆中性化 单元测试。"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.generation_service import (
    _structure_for_project,
    build_state_summary,
    extract_world_state_delta,
    generate_architecture,
    generate_chapter_draft,
    generate_directory,
)


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
        story_shape="final",
        total_chapters_target=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


_LLM = {"api_key": "test-key"}

_DIRECTORY = "第1章 - 开篇\n本章简述：开场。\n\n第2章 - 发展\n本章简述：推进。\n\n第3章 - 收束\n本章简述：收尾。"


class TestStructureForProject:
    def test_reads_structure(self):
        assert _structure_for_project(_project()) == "日常流"

    def test_none_without_writing_config(self):
        assert _structure_for_project(_project(writing_config=None)) is None

    def test_none_for_blank_or_non_string(self):
        assert _structure_for_project(_project(writing_config={"structure": ""})) is None
        assert _structure_for_project(_project(writing_config={"structure": 123})) is None


class TestGenerateWiring:
    """generate_architecture / generate_directory / generate_chapter_draft 注入新占位符。"""

    @patch("app.services.generation_service._make_adapter")
    def test_architecture_calm_fragments_injected(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        _run(generate_architecture(_project(), llm_config=_LLM))
        seed, char, world = adapter.prompts[0], adapter.prompts[1], adapter.prompts[2]
        # seed：平静分片（含"隐藏更大危机"否定语境，不含危机公式"隐藏的更大危机"）
        assert "隐藏更大危机" in seed
        assert "隐藏的更大危机" not in seed
        # character：平静分片特征（无危机弧线"蜕变节点"，温和渐进）
        assert "蜕变节点" not in char
        assert "温和渐进" in char
        # world：平静社会维度
        assert "生活方式与风俗习惯" in world
        assert "权力结构断层线" not in world

    @patch("app.services.generation_service._make_adapter")
    def test_architecture_old_project_crisis_baseline(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        old = _project(writing_config=None)
        _run(generate_architecture(old, llm_config=_LLM))
        seed, char, world = adapter.prompts[0], adapter.prompts[1], adapter.prompts[2]
        assert "隐藏的更大危机" in seed          # 危机公式
        assert "认知失调" in char               # 危机角色弧线
        assert "权力结构断层线" in world        # 危机社会维度

    @patch("app.services.generation_service._make_adapter")
    def test_directory_calm_blueprint(self, mock_adapter):
        adapter = CapturingAdapter(_DIRECTORY)   # 响应须可被 parse_chapter_blueprint 解析
        mock_adapter.return_value = adapter
        _run(generate_directory(_project(), architecture_text="架构", llm_config=_LLM))
        prompt = adapter.prompts[0]
        assert "本章变化" in prompt              # 平静蓝图分片
        assert "核心悬念类型" not in prompt

    @patch("app.services.generation_service._make_adapter")
    def test_first_chapter_injects_methodology_and_calm_guidance(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        _run(generate_chapter_draft(
            _project(), chapter_num=1,
            architecture_text="架构", directory_text=_DIRECTORY,
            llm_config=_LLM,
        ))
        prompt = adapter.prompts[0]
        # 题材方法论：伏笔间距 / 钩子偏好渲染片段
        assert "伏笔回收间距" in prompt
        assert "章末钩子偏好" in prompt
        # 平静首章分片：生活切片 / 不强求异常征兆
        assert "生活切片" in prompt
        assert "不强求异常征兆" in prompt

    @patch("app.services.generation_service._make_adapter")
    def test_next_chapter_injects_hook_preference(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        suspense = _project(genre="悬疑")   # 悬疑 hook_preference = 发现/误判
        _run(generate_chapter_draft(
            suspense, chapter_num=2,
            architecture_text="架构", directory_text=_DIRECTORY,
            character_state_text="角色状态",
            previous_chapter_draft="前文" * 500,
            previous_chapter_summary="前章概要",
            llm_config=_LLM,
        ))
        prompt = adapter.prompts[0]
        assert "（发现、误判 优先）" in prompt
        assert "伏笔回收间距" in prompt

    @patch("app.services.generation_service._make_adapter")
    def test_old_project_chapter_crisis_baseline(self, mock_adapter):
        adapter = CapturingAdapter()
        mock_adapter.return_value = adapter
        old = _project(writing_config=None)
        _run(generate_chapter_draft(
            old, chapter_num=1,
            architecture_text="架构", directory_text=_DIRECTORY,
            llm_config=_LLM,
        ))
        prompt = adapter.prompts[0]
        assert "埋下至少 2 个异常征兆" in prompt
        assert "打破平衡" in prompt


class TestMemoryNeutralization:
    """平静结构下 world_state 提取/摘要的中性化约束。"""

    @patch("app.services.generation_service._make_adapter")
    def test_extract_delta_calm_appends_suffix(self, mock_adapter):
        adapter = CapturingAdapter("""{"changed_in_chapter": 1, "no_changes": true}""")
        mock_adapter.return_value = adapter
        _run(extract_world_state_delta(
            "正文", 1, {}, {"description": "模板"}, llm_config=_LLM, structure="日常流",
        ))
        assert "平静结构补充" in adapter.prompts[0]
        assert "关键常态状态" in adapter.prompts[0]

    @patch("app.services.generation_service._make_adapter")
    def test_extract_delta_default_no_suffix(self, mock_adapter):
        adapter = CapturingAdapter("""{"changed_in_chapter": 1, "no_changes": true}""")
        mock_adapter.return_value = adapter
        _run(extract_world_state_delta("正文", 1, {}, {"description": "模板"}, llm_config=_LLM))
        assert "平静结构补充" not in adapter.prompts[0]

    @patch("app.services.generation_service._make_adapter")
    def test_summary_calm_appends_suffix(self, mock_adapter):
        adapter = CapturingAdapter("摘要条目")
        mock_adapter.return_value = adapter
        _run(build_state_summary(
            {"characters": {"张三": {}}}, target_chapter=2,
            chapter_title="标题", chapter_summary="简述",
            llm_config=_LLM, structure="群像交织",
        ))
        assert "平静结构补充" in adapter.prompts[0]
        assert "舒适/日常状态" in adapter.prompts[0]

    @patch("app.services.generation_service._make_adapter")
    def test_summary_default_no_suffix(self, mock_adapter):
        adapter = CapturingAdapter("摘要条目")
        mock_adapter.return_value = adapter
        _run(build_state_summary(
            {"characters": {"张三": {}}}, target_chapter=2,
            chapter_title="标题", chapter_summary="简述",
            llm_config=_LLM,
        ))
        assert "平静结构补充" not in adapter.prompts[0]

    def test_summary_calm_keeps_more_entities(self):
        """平静结构 slim_state 每类保留上限 20 条；缺省仍为 10 条。"""
        entities = {f"角色{i}": {"状态": "稳定"} for i in range(30)}

        # 平静结构：不触发 LLM，只验证裁剪逻辑（直接构造 prompt 前 inspect）
        from unittest.mock import AsyncMock
        with patch("app.services.generation_service._make_adapter") as m:
            m.return_value = CapturingAdapter("ok")
            _run(build_state_summary(
                {"characters": entities}, target_chapter=5,
                chapter_title="标题", chapter_summary="简述",
                llm_config=_LLM, structure="日常流",
            ))
        calm_body = json.loads(m.return_value.prompts[0].split("【世界状态记录】", 1)[1].split("【本章信息】", 1)[0].strip())
        assert len(calm_body["characters"]) == 20

        with patch("app.services.generation_service._make_adapter") as m2:
            m2.return_value = CapturingAdapter("ok")
            _run(build_state_summary(
                {"characters": entities}, target_chapter=5,
                chapter_title="标题", chapter_summary="简述",
                llm_config=_LLM,
            ))
        crisis_body = json.loads(m2.return_value.prompts[0].split("【世界状态记录】", 1)[1].split("【本章信息】", 1)[0].strip())
        assert len(crisis_body["characters"]) == 10
