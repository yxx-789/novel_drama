# test_character_cards.py
# -*- coding: utf-8 -*-
"""P2-B 角色卡系统：渲染 / 写前加载 / 写后更新 单元测试。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.generator.prompts import character_card_update_prompt
from app.services.generation_service import (
    _render_character_cards,
    load_active_character_cards,
    update_character_cards,
)


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


class _FakeAsset:
    def __init__(self, content_text=None, content_json=None):
        self.asset_type = "characters"
        self.content_text = content_text
        self.content_json = content_json
        self.version = 0


class _FakeResultOne:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeResultAll:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


class _FakeCharacterDB:
    """模拟 AsyncSession：按 SQL 关键字分发 asset / chapter 查询。"""

    def __init__(self, asset=None, prev_chapter=None):
        self.asset = asset
        self.prev_chapter = prev_chapter
        self.commit_count = 0
        self.added = []

    async def commit(self):
        self.commit_count += 1

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, query):
        sql = str(query.compile())
        if "asset_type" in sql:
            return _FakeResultOne(self.asset)
        if "chapter_num" in sql:
            return _FakeResultOne(self.prev_chapter)
        return _FakeResultAll([])


def _cards_json():
    return {
        "characters": {
            "张三": {
                "profile": "剑修",
                "current_state": {"情绪": "平静"},
                "relations": {"李四": "师门"},
                "known": ["知道山门将封"],
                "last_appearance": 3,
                "trajectory": ["第1章入门"],
            },
            "李四": {
                "profile": "炼器师",
                "current_state": {"状态": "重伤"},
                "relations": {"张三": "师门"},
                "known": [],
                "last_appearance": 2,
                "trajectory": [],
            },
            "王二": {
                "profile": "凡人商贩",
                "current_state": {},
                "relations": {},
                "known": [],
                "last_appearance": 1,
                "trajectory": [],
            },
        }
    }


class TestRenderCharacterCards:
    def test_renders_all_when_no_active_names(self):
        text = _render_character_cards(_cards_json())
        assert "### 张三" in text
        assert "### 李四" in text
        assert "### 王二" in text
        assert "人设：剑修" in text
        assert "最近出场：第3章" in text

    def test_renders_only_active_names(self):
        text = _render_character_cards(_cards_json(), active_names=["张三"])
        assert "### 张三" in text
        assert "### 李四" not in text
        assert "### 王二" not in text

    def test_malformed_input_returns_empty(self):
        assert _render_character_cards(None) == ""
        assert _render_character_cards({"foo": 1}) == ""
        assert _render_character_cards({}) == ""

    def test_malformed_card_degrades_gracefully(self):
        data = {"characters": {"张三": "不是dict", "李四": {"profile": "OK"}}}
        text = _render_character_cards(data)
        assert "### 张三" in text
        assert "人设：OK" in text


class TestLoadActiveCharacterCards:
    def test_json_project_loads_only_active_cards(self):
        prev = SimpleNamespace(
            actual_summary_json={"summary": "s", "characters": ["张三", "王二"]}
        )
        db = _FakeCharacterDB(asset=_FakeAsset(content_json=_cards_json()), prev_chapter=prev)
        text = _run(load_active_character_cards(db, str(uuid.uuid4()), chapter_num=4))
        assert "### 张三" in text
        assert "### 王二" in text
        assert "### 李四" not in text  # 上一章未出场 → 不注入

    def test_chapter_one_falls_back_to_all_cards(self):
        db = _FakeCharacterDB(asset=_FakeAsset(content_json=_cards_json()), prev_chapter=None)
        text = _run(load_active_character_cards(db, str(uuid.uuid4()), chapter_num=1))
        assert "### 张三" in text
        assert "### 李四" in text
        assert "### 王二" in text

    def test_prev_chapter_no_characters_falls_back_to_all(self):
        prev = SimpleNamespace(actual_summary_json={"summary": "s"})
        db = _FakeCharacterDB(asset=_FakeAsset(content_json=_cards_json()), prev_chapter=prev)
        text = _run(load_active_character_cards(db, str(uuid.uuid4()), chapter_num=3))
        assert "### 王二" in text

    def test_old_text_project_returns_text_as_is(self):
        old_text = "张三：\n├──物品：……"
        db = _FakeCharacterDB(asset=_FakeAsset(content_text=old_text))
        text = _run(load_active_character_cards(db, str(uuid.uuid4()), chapter_num=5))
        assert text == old_text

    def test_no_asset_returns_empty(self):
        db = _FakeCharacterDB(asset=None)
        assert _run(load_active_character_cards(db, str(uuid.uuid4()), chapter_num=1)) == ""


class TestUpdateCharacterCards:
    def _db_with_asset(self, asset):
        return _FakeCharacterDB(asset=asset)

    @patch("app.services.generation_service._make_adapter")
    def test_success_updates_and_writes_dual_channel(self, mock_make_adapter):
        raw_json = (
            '{"characters": {"张三": {"profile": "剑修", "current_state": {"情绪": "兴奋"},'
            ' "relations": {"李四": "师门"}, "known": ["知道山门将封"],'
            ' "trajectory": ["第1章入门", "第4章突破"]}}}'
        )
        mock_make_adapter.return_value = FakeAdapter(raw_json)
        asset = _FakeAsset(content_json=_cards_json())
        db = self._db_with_asset(asset)
        result = _run(update_character_cards(db, str(uuid.uuid4()), 4, "第四章正文" * 200, {"api_key": "t"}))

        assert result is not None
        assert "张三" in result["characters"]
        # 双通道写回
        assert asset.content_json is not None
        assert "张三" in asset.content_json["characters"]
        assert "人设：剑修" in (asset.content_text or "")
        assert asset.version == 1
        assert db.commit_count == 1
        # 缺失 last_appearance → 兜底为本章号
        assert result["characters"]["张三"]["last_appearance"] == 4

    @patch("app.services.generation_service._make_adapter")
    def test_old_text_input_migrates_to_json(self, mock_make_adapter):
        raw_json = '{"characters": {"张三": {"profile": "剑修", "current_state": {"状态": "轻伤"}, "last_appearance": 2}}}'
        mock_make_adapter.return_value = FakeAdapter(raw_json)
        asset = _FakeAsset(content_text="张三：\n├──物品：……")  # 旧版文本
        db = self._db_with_asset(asset)
        result = _run(update_character_cards(db, str(uuid.uuid4()), 2, "第二章正文" * 100, {"api_key": "t"}))
        assert result is not None
        assert asset.content_json == result
        assert "人设：剑修" in (asset.content_text or "")

    @patch("app.services.generation_service._make_adapter")
    def test_invalid_json_returns_none_keeps_old_state(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter("这不是 JSON")
        asset = _FakeAsset(content_json=_cards_json())
        db = self._db_with_asset(asset)
        result = _run(update_character_cards(db, str(uuid.uuid4()), 3, "正文" * 100, {"api_key": "t"}))
        assert result is None
        assert asset.content_json == _cards_json()  # 旧状态保留
        assert asset.version == 0

    @patch("app.services.generation_service._make_adapter")
    def test_llm_exception_returns_none(self, mock_make_adapter):
        mock_make_adapter.return_value = FakeAdapter(error=RuntimeError("LLM down"))
        asset = _FakeAsset(content_json=_cards_json())
        db = self._db_with_asset(asset)
        result = _run(update_character_cards(db, str(uuid.uuid4()), 3, "正文" * 100, {"api_key": "t"}))
        assert result is None

    @patch("app.services.generation_service.settings.LLM_API_KEY", "")
    def test_llm_not_configured_returns_none(self):
        db = self._db_with_asset(_FakeAsset(content_json=_cards_json()))
        assert _run(update_character_cards(db, str(uuid.uuid4()), 3, "正文" * 100, None)) is None

    def test_empty_chapter_text_returns_none(self):
        db = self._db_with_asset(_FakeAsset(content_json=_cards_json()))
        assert _run(update_character_cards(db, str(uuid.uuid4()), 3, "", {"api_key": "t"})) is None

    def test_no_asset_creates_new_asset(self):
        with patch("app.services.generation_service._make_adapter") as mock_make_adapter:
            mock_make_adapter.return_value = FakeAdapter(
                '{"characters": {"张三": {"profile": "剑修", "current_state": {"状态": "好"}, "last_appearance": 1}}}'
            )
            db = _FakeCharacterDB(asset=None)
            result = _run(update_character_cards(db, str(uuid.uuid4()), 1, "第一章正文" * 100, {"api_key": "t"}))
            assert result is not None
            assert len(db.added) == 1
            assert db.added[0].asset_type == "characters"
            assert db.added[0].content_json == result


class TestCharacterCardUpdatePrompt:
    def test_prompt_has_required_placeholders(self):
        assert "{chapter_text}" in character_card_update_prompt
        assert "{old_state}" in character_card_update_prompt
        # 防回归：prompt 明确要求保留未出场角色
        assert "原样保留" in character_card_update_prompt
