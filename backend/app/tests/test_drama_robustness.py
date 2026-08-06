"""短剧大纲 JSON 解析鲁棒性 + LLM 输出清洗单元测试"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# 确保 app 目录在路径中
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.generator.llm_utils import repair_stray_quotes
from app.services import drama_service
from app.services.drama_service import (
    _OUTLINE_PARSE_MAX_RETRIES,
    _parse_llm_json,
    generate_drama_outline,
)
from app.services.generation_service import _parse_llm_json as gen_parse_llm_json


class TestRepairStrayQuotes:
    """repair_stray_quotes 定点修复逻辑"""

    def test_repairs_quotes_inside_cjk(self):
        # 复现线上失败样例：dialogue 字段内嵌英文双引号
        text = '{"dialogue": "（OS 咪咪心声）"今天必须吃到那条鱼。", "x": 1}'
        repaired = repair_stray_quotes(text)
        parsed = json.loads(repaired)
        assert parsed["x"] == 1
        assert "今天必须吃到那条鱼" in parsed["dialogue"]

    def test_clean_json_untouched(self):
        text = '{"a": "杏花村", "b": 1}'
        assert repair_stray_quotes(text) == text

    def test_ascii_content_untouched(self):
        # 两侧非中文字符的双引号不处理（可能是结构引号或英文内容）
        text = '{"dialogue": "hello world", "x": 1}'
        assert repair_stray_quotes(text) == text

    def test_empty_returns_input_idempotently(self):
        assert repair_stray_quotes("") == ""
        assert repair_stray_quotes(None) is None


class TestParseLlmeJsonRepair:
    """_parse_llm_json 新增 repair fallback candidate"""

    def test_drama_parser_repairs_stray_quotes(self):
        raw = 'json\n{"dialogue": "（OS 咪咪心声）"今天必须吃到那条鱼。", "x": 1}'
        result = _parse_llm_json(raw)
        assert result is not None
        assert result["x"] == 1
        assert "今天必须吃到那条鱼" in result["dialogue"]

    def test_generation_parser_repairs_stray_quotes(self):
        raw = '{"dialogue": "（OS 咪咪心声）"今天必须吃到那条鱼。", "x": 1}'
        result = gen_parse_llm_json(raw)
        assert result is not None
        assert result["x"] == 1

    def test_degenerate_json_prefix_returns_none(self):
        # 只有 "json"（退化输出）无法解析为 dict
        assert _parse_llm_json("json") is None


class TestGenerateDramaOutlineRetry:
    """generate_drama_outline 解析失败自动带提示重试"""

    VALID_OUTLINE = json.dumps(
        {
            "episode_num": 1,
            "title": "橘猫剑主",
            "chapters_covered": "第 1-3 章",
            "duration_estimate": "120 秒",
            "hook": {"first_3s": {"visual": "v", "action": "a", "dialogue": "d"}},
            "story_beats": [
                {
                    "beat_num": 1,
                    "type": "setup",
                    "description": "x",
                    "key_info": "k",
                    "emotion": "e",
                    "duration": "15 秒",
                }
            ],
            "cliffhanger": {
                "last_5s": {"visual": "v", "action": "a", "dialogue": "d", "suspense_type": "情节"}
            },
            "key_characters": ["咪咪"],
            "reversal_count": 1,
            "爽点_tags": ["逆袭"],
            "key_items": ["锈剑"],
            "adaptation_notes": "n",
        },
        ensure_ascii=False,
    )

    @staticmethod
    async def _call(side_effect):
        with patch.object(
            drama_service, "_invoke_llm", new=AsyncMock(side_effect=side_effect)
        ) as mock:
            outline = await generate_drama_outline(
                chapter_texts="=== 第1章 ===\n正文",
                characters_text="角色设定",
                episode_num=1,
                chapters_range="第 1-3 章",
            )
        return outline, mock

    def test_first_parse_succeeds(self):
        outline, mock = asyncio.run(self._call([self.VALID_OUTLINE]))
        assert outline["episode_num"] == 1
        assert outline["title"] == "橘猫剑主"
        mock.assert_awaited_once()

    def test_retries_on_unfixable_malformed_then_succeeds(self):
        # 英文内容内嵌引号：repair 规则不命中 → 解析失败 → 重试成功
        garbage = 'json\n{"dialogue": "hello"world", "x": 1}'
        outline, mock = asyncio.run(self._call([garbage, self.VALID_OUTLINE]))
        assert outline["title"] == "橘猫剑主"
        assert mock.await_count == 2
        # 第二次调用带上了修复提示
        prompts = [c.args[0] for c in mock.await_args_list]
        assert "无法解析" in prompts[1]

    def test_retries_on_degenerate_output(self):
        # 退化输出只有 "json"
        outline, mock = asyncio.run(self._call(["json", self.VALID_OUTLINE]))
        assert outline["episode_num"] == 1
        assert mock.await_count == 2

    def test_all_fail_raises(self):
        async def _inner():
            with patch.object(
                drama_service, "_invoke_llm", new=AsyncMock(side_effect=["json"] * 10)
            ) as mock:
                with pytest.raises(
                    RuntimeError, match="Failed to parse drama outline JSON for episode 1"
                ):
                    await generate_drama_outline(
                        chapter_texts="正文",
                        characters_text="角色",
                        episode_num=1,
                        chapters_range="第 1 章",
                    )
            return mock

        mock = asyncio.run(_inner())
        assert mock.await_count == _OUTLINE_PARSE_MAX_RETRIES


class TestInvokeLlmDegenerateRetry:
    """_invoke_llm 把退化 "json" 输出视为空并重试（原始 bug 的直接防线）"""

    @staticmethod
    def _config():
        return {
            "api_key": "test-key",
            "base_url": "http://localhost:9999/v1",
            "model": "test-model",
            "interface_format": "openai",
            "temperature": 0.7,
            "max_tokens": 100,
            "timeout": 30,
        }

    def test_json_only_output_is_retried(self):
        async def _inner():
            adapter = AsyncMock()
            adapter.invoke = AsyncMock(side_effect=["```json", "```json\n{\"ok\": true}"])
            with patch.object(drama_service, "create_llm_adapter", return_value=adapter):
                result = await drama_service._invoke_llm("prompt", llm_config=self._config())
            return result, adapter

        result, adapter = asyncio.run(_inner())
        assert result == 'json\n{"ok": true}'
        assert adapter.invoke.await_count == 2

    def test_real_json_output_returns_immediately(self):
        async def _inner():
            adapter = AsyncMock()
            adapter.invoke = AsyncMock(side_effect=["```json\n{\"ok\": true}"])
            with patch.object(drama_service, "create_llm_adapter", return_value=adapter):
                result = await drama_service._invoke_llm("prompt", llm_config=self._config())
            return result, adapter

        result, adapter = asyncio.run(_inner())
        assert result == 'json\n{"ok": true}'
        assert adapter.invoke.await_count == 1
