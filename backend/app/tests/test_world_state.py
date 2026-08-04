"""World State 核心逻辑单元测试"""

import pytest
import sys
from pathlib import Path

# 确保 app 目录在路径中
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.generator.world_state_templates import get_template, GENERIC_TEMPLATE, XIANXIA_TEMPLATE, URBAN_TEMPLATE
from app.services.generation_service import _parse_llm_json, merge_world_state


class TestGetTemplate:
    """测试模板选择逻辑"""

    def test_empty_genre_returns_generic(self):
        assert get_template("") is GENERIC_TEMPLATE
        assert get_template(None) is GENERIC_TEMPLATE

    def test_xianxia_keywords(self):
        keywords = ["修仙", "玄幻", "仙侠", "修真", "武侠", "Xianxia", "Wuxia", "FANTASY"]
        for kw in keywords:
            result = get_template(kw)
            assert result is XIANXIA_TEMPLATE, f"'{kw}' should match xianxia template"

    def test_urban_keywords(self):
        keywords = ["都市", "现代", "商战", "系统", "重生", "Urban", "MODERN", "sys"]
        for kw in keywords:
            result = get_template(kw)
            assert result is URBAN_TEMPLATE, f"'{kw}' should match urban template"

    def test_unknown_genre_returns_generic(self):
        assert get_template("历史") is GENERIC_TEMPLATE
        assert get_template("科幻") is GENERIC_TEMPLATE
        assert get_template("悬疑") is GENERIC_TEMPLATE

    def test_mixed_genre_prefers_xianxia_over_urban(self):
        # 修仙 + 都市 混合时，修仙关键词优先匹配
        result = get_template("都市修仙")
        assert result is XIANXIA_TEMPLATE


class TestParseLLMJson:
    """测试 LLM JSON 输出解析鲁棒性"""

    def test_plain_json(self):
        raw = '{"key": "value", "num": 42}'
        result = _parse_llm_json(raw)
        assert result == {"key": "value", "num": 42}

    def test_json_with_markdown_code_block(self):
        raw = '''```json
{"characters": {"张三": {"realm": "筑基"}}}
```'''
        result = _parse_llm_json(raw)
        assert result == {"characters": {"张三": {"realm": "筑基"}}}

    def test_json_prefix_stripped(self):
        raw = 'json\n{"no_changes": true}'
        result = _parse_llm_json(raw)
        assert result == {"no_changes": True}

    def test_json_prefix_case_insensitive(self):
        raw = 'JSON  {"no_changes": true}'
        result = _parse_llm_json(raw)
        assert result == {"no_changes": True}

    def test_nested_json_in_text(self):
        raw = 'Here is the result:\n\n{"delta": {"characters": {}}}'
        result = _parse_llm_json(raw)
        assert result == {"delta": {"characters": {}}}

    def test_invalid_json_returns_none(self):
        assert _parse_llm_json("not json at all") is None
        assert _parse_llm_json("") is None
        assert _parse_llm_json(None) is None

    def test_list_json_returns_none(self):
        # _parse_llm_json 要求返回 dict，list 应该返回 None
        assert _parse_llm_json('[1, 2, 3]') is None

    def test_trailing_garbage_ignored(self):
        raw = '{"key": "value"} some extra text'
        result = _parse_llm_json(raw)
        assert result == {"key": "value"}


class TestMergeWorldState:
    """测试状态合并与变更历史记录"""

    def test_merge_new_character(self):
        old = {"characters": {}, "events": {}, "world": {}, "history": []}
        delta = {
            "changed_in_chapter": 3,
            "characters": {
                "张三": {"realm": "筑基", "changed_fields": ["realm"]}
            }
        }
        result = merge_world_state(old, delta)

        assert result["characters"]["张三"]["realm"] == "筑基"
        assert len(result["history"]) == 1
        assert result["history"][0]["chapter"] == 3
        assert len(result["history"][0]["changes"]) == 1
        assert result["history"][0]["changes"][0]["entity"] == "张三"
        assert result["history"][0]["changes"][0]["field"] == "realm"
        assert result["history"][0]["changes"][0]["from"] is None
        assert result["history"][0]["changes"][0]["to"] == "筑基"

    def test_merge_update_existing_field(self):
        old = {
            "characters": {"张三": {"realm": "练气", "items": "铁剑"}},
            "history": []
        }
        delta = {
            "changed_in_chapter": 5,
            "characters": {
                "张三": {"realm": "筑基", "changed_fields": ["realm"]}
            }
        }
        result = merge_world_state(old, delta)

        assert result["characters"]["张三"]["realm"] == "筑基"
        # 未变更字段保留
        assert result["characters"]["张三"]["items"] == "铁剑"
        # 历史记录正确
        change = result["history"][0]["changes"][0]
        assert change["from"] == "练气"
        assert change["to"] == "筑基"

    def test_merge_no_changes(self):
        old = {"characters": {}, "history": []}
        delta = {"changed_in_chapter": 2, "no_changes": True}
        result = merge_world_state(old, delta)

        assert len(result["history"]) == 1
        assert result["history"][0]["changes"] == []

    def test_merge_multiple_categories(self):
        old = {"characters": {}, "events": {}, "world": {}, "history": []}
        delta = {
            "changed_in_chapter": 10,
            "characters": {
                "张三": {"realm": "金丹", "changed_fields": ["realm"]}
            },
            "events": {
                "宗门大比": {"status": "进行中", "changed_fields": ["status"]}
            }
        }
        result = merge_world_state(old, delta)

        assert len(result["history"][0]["changes"]) == 2
        categories = {c["category"] for c in result["history"][0]["changes"]}
        assert categories == {"characters", "events"}

    def test_merge_preserves_existing_history(self):
        old = {
            "characters": {},
            "history": [{"chapter": 1, "changes": [{"entity": "张三", "field": "realm", "from": None, "to": "练气"}]}]
        }
        delta = {
            "changed_in_chapter": 2,
            "characters": {"张三": {"realm": "筑基", "changed_fields": ["realm"]}}
        }
        result = merge_world_state(old, delta)

        assert len(result["history"]) == 2
        assert result["history"][0]["chapter"] == 1
        assert result["history"][1]["chapter"] == 2

    def test_merge_same_value_no_history(self):
        """字段值未改变时不应记录历史"""
        old = {"characters": {"张三": {"realm": "筑基"}}, "history": []}
        delta = {
            "changed_in_chapter": 3,
            "characters": {"张三": {"realm": "筑基", "changed_fields": ["realm"]}}
        }
        result = merge_world_state(old, delta)

        assert result["characters"]["张三"]["realm"] == "筑基"
        assert len(result["history"][0]["changes"]) == 0

    def test_merge_creates_missing_categories(self):
        old = {"characters": {}}
        delta = {
            "changed_in_chapter": 1,
            "world": {"灵气潮汐": {"status": "涨潮", "changed_fields": ["status"]}}
        }
        result = merge_world_state(old, delta)

        assert "world" in result
        assert result["world"]["灵气潮汐"]["status"] == "涨潮"

    def test_merge_flat_world_structure(self):
        """回归：world 按 prompt 模板为扁平结构（字段->值），不应按实体嵌套处理导致崩溃"""
        old = {"world": {"current_date": "第1天"}, "history": []}
        delta = {
            "changed_in_chapter": 2,
            "world": {"changed_fields": ["current_date"], "current_date": "第3天"}
        }
        result = merge_world_state(old, delta)

        assert result["world"]["current_date"] == "第3天"
        change = result["history"][0]["changes"][0]
        assert change["category"] == "world"
        assert change["field"] == "current_date"
        assert change["from"] == "第1天"
        assert change["to"] == "第3天"

    def test_merge_nested_world_structure_still_works(self):
        """兼容：历史数据/部分模板 world 仍为实体嵌套结构"""
        old = {"world": {}, "history": []}
        delta = {
            "changed_in_chapter": 1,
            "world": {"灵气潮汐": {"status": "涨潮", "changed_fields": ["status"]}}
        }
        result = merge_world_state(old, delta)
        assert result["world"]["灵气潮汐"]["status"] == "涨潮"

    def test_deep_copy_no_mutation(self):
        """merge 不应修改原 state"""
        old = {"characters": {"张三": {"realm": "练气"}}, "history": []}
        delta = {
            "changed_in_chapter": 2,
            "characters": {"张三": {"realm": "筑基", "changed_fields": ["realm"]}}
        }
        merge_world_state(old, delta)

        # 原 state 不应被修改
        assert old["characters"]["张三"]["realm"] == "练气"
        assert old["history"] == []
