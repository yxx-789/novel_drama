# test_p3b_wiring.py
# -*- coding: utf-8 -*-
"""V3 P3-B 记忆分层接线：task_service 写前/写后钩子 + 资产读写 + LLM 调用数约束 单测。"""

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.task_service import (
    _build_l2_foreshadowing_context,
    _finalize_arc_summary,
    _get_asset_json,
    _merge_foreshadowing_ledger,
    _save_asset_json,
    _synthesize_book_summary_asset,
    run_batch_chapters_task,
    run_chapter_task,
    ARC_SIZE,
)


def _run(coro):
    return asyncio.run(coro)


# ==================== 伪 AsyncSession（支持资产 + 章节查询） ====================

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


PROJECT_ID = "00000000-0000-0000-0000-000000000001"


class _FakeAsset:
    """模拟 ProjectAsset：存 content_json / content_text。"""

    def __init__(self, asset_type, content_json=None, content_text=None, version=1):
        self.project_id = PROJECT_ID
        self.asset_type = asset_type
        self.content_json = content_json
        self.content_text = content_text
        self.version = version
        self.id = None
        self.updated_at = None
        self.updated_by = None


def _has_param(params, name):
    return any(k.startswith(name) for k in params)


class _FakeDB:
    """模拟 AsyncSession：

    - ProjectAsset 查询（project_id + asset_type）
    - Chapter 列表 / 前章（chapter_num ==） / arc 范围（>= start <= end）
    """

    def __init__(self, chapters=None, assets=None):
        self.chapters = list(chapters or [])
        self.assets = {a.asset_type: a for a in (assets or [])}
        self.commit_count = 0

    async def commit(self):
        self.commit_count += 1

    async def execute(self, query):
        compiled = query.compile()
        sql = str(compiled)
        params = compiled.params
        if "asset_type" in sql:
            at = next(v for k, v in params.items() if k.startswith("asset_type"))
            return _FakeResultOne(self.assets.get(at))
        nums = [v for k, v in params.items() if k.startswith("chapter_num")]
        if nums:
            if len(nums) >= 2:
                lo, hi = min(nums), max(nums)
                return _FakeResultAll([c for c in self.chapters if lo <= c.chapter_num <= hi])
            num = nums[0]
            row = next((c for c in self.chapters if c.chapter_num == num), None)
            return _FakeResultOne(row)
        return _FakeResultAll(self.chapters)

    def add(self, asset):
        self.assets[asset.asset_type] = asset


class _FakeSessionFactory:
    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        return False


def _mk_chapter(num, outline="大纲", draft=None):
    return SimpleNamespace(
        chapter_num=num,
        outline=outline,
        actual_summary_json=None,
        draft=draft,
        status="pending",
        title=f"第{num}章",
    )


# ==================== 资产读写 ====================

class TestAssetJson:
    def test_get_returns_content_json(self):
        db = _FakeDB(assets=[_FakeAsset("foreshadowing", content_json={"entries": []})])
        assert _run(_get_asset_json(db, PROJECT_ID, "foreshadowing")) == {"entries": []}

    def test_get_missing_returns_none(self):
        db = _FakeDB()
        assert _run(_get_asset_json(db, PROJECT_ID, "arc_summaries")) is None

    def test_get_non_dict_content_json_returns_none(self):
        db = _FakeDB(assets=[_FakeAsset("foreshadowing", content_json="not a dict")])
        assert _run(_get_asset_json(db, PROJECT_ID, "foreshadowing")) is None

    def test_save_updates_existing_asset(self):
        asset = _FakeAsset("foreshadowing", content_json={"entries": []}, version=1)
        db = _FakeDB(assets=[asset])
        _run(_save_asset_json(db, PROJECT_ID, "foreshadowing", {"entries": [{"name": "x"}]}))
        assert asset.content_json == {"entries": [{"name": "x"}]}
        assert asset.version == 2
        assert db.commit_count == 1

    def test_save_creates_new_asset(self):
        db = _FakeDB()
        _run(_save_asset_json(db, PROJECT_ID, "arc_summaries", {"arcs": []}))
        assert db.assets["arc_summaries"].content_json == {"arcs": []}


# ==================== L2 上下文组装 ====================

class TestBuildL2Context:
    def test_no_assets_returns_empty(self):
        db = _FakeDB()
        assert _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 5, "玄幻")) == ""

    def test_includes_frozen_arc_summary(self):
        db = _FakeDB(assets=[_FakeAsset("arc_summaries", content_json={
            "arcs": [{"arc_index": 0, "summary": "前15章剧情摘要"}],
        })])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 16, "玄幻"))
        assert "前15章剧情摘要" in ctx

    def test_includes_foreshadowing_reminder(self):
        db = _FakeDB(assets=[_FakeAsset("foreshadowing", content_json={
            "entries": [{
                "name": "铜匣", "status": "open", "added_chapter": 1,
                "last_touch_chapter": 1, "planned_recovery_range": [20, 40],
            }],
            "unmatched": [],
        })])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 35, "玄幻"))
        assert "伏笔" in ctx
        assert "铜匣" in ctx

    def test_combines_both_sections(self):
        db = _FakeDB(assets=[
            _FakeAsset("arc_summaries", content_json={
                "arcs": [{"arc_index": 0, "summary": "arc 摘要内容"}],
            }),
            _FakeAsset("foreshadowing", content_json={
                "entries": [{
                    "name": "铜匣", "status": "open", "added_chapter": 1,
                    "last_touch_chapter": 1, "planned_recovery_range": [20, 40],
                }],
                "unmatched": [],
            }),
        ])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 35, "玄幻"))
        assert "arc 摘要内容" in ctx
        assert "铜匣" in ctx

    def test_empty_arc_summary_string_skipped(self):
        db = _FakeDB(assets=[_FakeAsset("arc_summaries", content_json={
            "arcs": [{"arc_index": 0, "summary": "   "}],
        })])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 16, "玄幻"))
        assert "arc 摘要" not in ctx

    # ---- P3-B 闭环：L3 全书脉络 + known_by 信息约束注入 ----

    def test_includes_book_summary_when_reminder_present(self):
        """伏笔提醒非空时注入 L3 全书脉络。"""
        db = _FakeDB(assets=[
            _FakeAsset("arc_summaries", content_json={
                "arcs": [{"arc_index": 0, "summary": "arc 摘要"}],
                "book_summary": {"summary": "全书脉络摘要"},
            }),
            _FakeAsset("foreshadowing", content_json={
                "entries": [{
                    "name": "铜匣", "status": "open", "added_chapter": 1,
                    "last_touch_chapter": 1, "planned_recovery_range": [20, 40],
                    "known_by": ["主角"],
                }],
                "unmatched": [],
            }),
        ])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 35, "玄幻"))
        assert "【全书脉络】" in ctx
        assert "全书脉络摘要" in ctx

    def test_skips_book_summary_when_no_reminder(self):
        """无伏笔提醒（无需回溯早期细节）时即使 book_summary 存在也不注入 L3。"""
        db = _FakeDB(assets=[
            _FakeAsset("arc_summaries", content_json={
                "arcs": [{"arc_index": 0, "summary": "arc 摘要"}],
                "book_summary": {"summary": "全书脉络摘要"},
            }),
            _FakeAsset("foreshadowing", content_json={"entries": [], "unmatched": []}),
        ])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 5, "玄幻"))
        assert "【全书脉络】" not in ctx

    def test_includes_known_by_constraints(self):
        """每章注入 known_by 信息约束（最近触碰伏笔的已知晓者）。"""
        db = _FakeDB(assets=[_FakeAsset("foreshadowing", content_json={
            "entries": [{
                "name": "玉佩", "status": "open", "added_chapter": 3,
                "last_touch_chapter": 3, "planned_recovery_range": [20, 40],
                "known_by": ["主角"],
            }],
            "unmatched": [],
        })])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 5, "玄幻"))
        assert "【信息约束】" in ctx
        assert "玉佩" in ctx
        assert "已知晓者" in ctx

    def test_skips_known_by_when_no_known(self):
        """无候选（known_by 为空 / 已回收）时不注入信息约束。"""
        db = _FakeDB(assets=[_FakeAsset("foreshadowing", content_json={
            "entries": [
                {"name": "A", "status": "open", "added_chapter": 1, "last_touch_chapter": 1,
                 "planned_recovery_range": [20, 40], "known_by": []},
                {"name": "B", "status": "recovered", "added_chapter": 1, "last_touch_chapter": 1,
                 "planned_recovery_range": [20, 40], "known_by": ["主角"]},
            ],
            "unmatched": [],
        })])
        ctx = _run(_build_l2_foreshadowing_context(db, PROJECT_ID, 5, "玄幻"))
        assert "【信息约束】" not in ctx


# ==================== 台账合并写回 ====================

class TestMergeLedger:
    def test_merges_memory_delta_into_asset(self):
        db = _FakeDB()
        memory = {
            "foreshadowing_added": [{"name": "铜匣", "note": "信物", "known_by": ["主角"]}],
            "foreshadowing_touched": [],
            "foreshadowing_recovered": [],
            "subplot_advanced": [],
        }
        _run(_merge_foreshadowing_ledger(db, PROJECT_ID, 3, memory, "玄幻"))
        asset = db.assets["foreshadowing"]
        entries = asset.content_json["entries"]
        assert len(entries) == 1
        assert entries[0]["name"] == "铜匣"
        assert entries[0]["status"] == "open"
        assert entries[0]["added_chapter"] == 3

    def test_initializes_absent_ledger(self):
        db = _FakeDB()
        _run(_merge_foreshadowing_ledger(db, PROJECT_ID, 1, {}, "玄幻"))
        assert "foreshadowing" in db.assets
        assert db.assets["foreshadowing"].content_json == {"entries": [], "unmatched": []}

    def test_failure_does_not_raise(self):
        # 查询抛异常 → 内部 try/except 吞掉，不中断生成
        db = _FakeDB()

        async def boom(*args, **kwargs):
            raise RuntimeError("db down")

        db.execute = boom
        _run(_merge_foreshadowing_ledger(db, PROJECT_ID, 3, {"foreshadowing_added": []}, "玄幻"))
        assert "foreshadowing" not in db.assets

    def test_no_change_does_not_bump_version(self):
        """merge 前后无变化（空 memory）→ 跳过写回，version / commit 均不变。"""
        asset = _FakeAsset("foreshadowing", content_json={"entries": [], "unmatched": []}, version=3)
        db = _FakeDB(assets=[asset])
        _run(_merge_foreshadowing_ledger(db, PROJECT_ID, 3, {}, "玄幻"))
        assert asset.version == 3
        assert db.commit_count == 0

    def test_no_change_with_empty_lists_skips(self):
        """memory 字段全是空列表 → 无变化 → 不写回。"""
        asset = _FakeAsset("foreshadowing", content_json={"entries": [], "unmatched": []}, version=3)
        db = _FakeDB(assets=[asset])
        memory = {
            "foreshadowing_added": [], "foreshadowing_touched": [],
            "foreshadowing_recovered": [], "subplot_advanced": [],
        }
        _run(_merge_foreshadowing_ledger(db, PROJECT_ID, 3, memory, "玄幻"))
        assert asset.version == 3
        assert db.commit_count == 0

    def test_change_still_writes_and_bumps_version(self):
        """已有资产且 merge 产生变化 → 写回 + version bump。"""
        asset = _FakeAsset("foreshadowing", content_json={"entries": [], "unmatched": []}, version=3)
        db = _FakeDB(assets=[asset])
        memory = {"foreshadowing_added": [{"name": "铜匣", "note": "信物"}]}
        _run(_merge_foreshadowing_ledger(db, PROJECT_ID, 3, memory, "玄幻"))
        assert asset.version == 4
        assert asset.content_json["entries"][0]["name"] == "铜匣"


# ==================== arc 边界冻结 ====================

class TestFinalizeArcSummary:
    def test_non_boundary_does_not_call_llm(self):
        db = _FakeDB(chapters=[_mk_chapter(1), _mk_chapter(2)])
        with patch("app.services.task_service.build_arc_summary") as mock_build:
            mock_build.return_value = {"summary": "arc", "chapter_range": [1, 2]}
            _run(_finalize_arc_summary(db, PROJECT_ID, 2, {"api_key": "k"}))
            mock_build.assert_not_called()
        assert "arc_summaries" not in db.assets

    @patch("app.services.task_service.ARC_SIZE", 2)
    def test_boundary_freezes_arc(self):
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with patch("app.services.task_service.build_arc_summary") as mock_build:
            mock_build.return_value = {"summary": "前两章剧情", "chapter_range": [1, 2]}
            _run(_finalize_arc_summary(db, PROJECT_ID, 2, {"api_key": "k"}))
            mock_build.assert_called_once()
        asset = db.assets["arc_summaries"]
        assert asset.content_json["arcs"][0]["arc_index"] == 0
        assert asset.content_json["arcs"][0]["chapter_range"] == [1, 2]
        assert asset.content_json["arcs"][0]["summary"] == "前两章剧情"

    @patch("app.services.task_service.ARC_SIZE", 2)
    def test_boundary_frozen_not_overwritten(self):
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with patch("app.services.task_service.build_arc_summary") as mock_build:
            mock_build.return_value = {"summary": "v1", "chapter_range": [1, 2]}
            _run(_finalize_arc_summary(db, PROJECT_ID, 2, {"api_key": "k"}))
            # 再次同边界 → 冻结不覆盖
            _run(_finalize_arc_summary(db, PROJECT_ID, 2, {"api_key": "k"}))
            mock_build.assert_called_once()
        arcs = db.assets["arc_summaries"].content_json["arcs"]
        assert len(arcs) == 1

    @patch("app.services.task_service.ARC_SIZE", 2)
    def test_empty_arc_result_skipped(self):
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with patch("app.services.task_service.build_arc_summary") as mock_build:
            mock_build.return_value = {}
            _run(_finalize_arc_summary(db, PROJECT_ID, 2, {"api_key": "k"}))
        assert "arc_summaries" not in db.assets

    @patch("app.services.task_service.ARC_SIZE", 2)
    def test_failure_does_not_raise(self):
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with patch("app.services.task_service.build_arc_summary") as mock_build:
            mock_build.side_effect = RuntimeError("LLM down")
            _run(_finalize_arc_summary(db, PROJECT_ID, 2, {"api_key": "k"}))
        assert "arc_summaries" not in db.assets


# ==================== 全书摘要合成 ====================

class TestSynthesizeBookSummaryAsset:
    def test_no_arcs_skips(self):
        db = _FakeDB(assets=[_FakeAsset("arc_summaries", content_json={"arcs": [], "book_summary": {}})])
        with patch("app.services.task_service.synthesize_book_summary") as mock_synth:
            _run(_synthesize_book_summary_asset(db, PROJECT_ID, {"api_key": "k"}))
            mock_synth.assert_not_called()

    @patch("app.services.task_service.ARC_SIZE", 2)
    def test_with_arcs_synthesizes(self):
        db = _FakeDB(assets=[_FakeAsset("arc_summaries", content_json={
            "arcs": [{"arc_index": 0, "chapter_range": [1, 2], "summary": "a"}],
            "book_summary": {},
        })])
        with patch("app.services.task_service.synthesize_book_summary") as mock_synth:
            mock_synth.return_value = "全书摘要"
            _run(_synthesize_book_summary_asset(db, PROJECT_ID, {"api_key": "k"}))
            mock_synth.assert_called_once()
        asset = db.assets["arc_summaries"]
        assert asset.content_json["book_summary"]["summary"] == "全书摘要"

    def test_empty_synthesis_skips_write(self):
        db = _FakeDB(assets=[_FakeAsset("arc_summaries", content_json={
            "arcs": [{"arc_index": 0, "summary": "a"}], "book_summary": {},
        })])
        with patch("app.services.task_service.synthesize_book_summary") as mock_synth:
            mock_synth.return_value = ""
            _run(_synthesize_book_summary_asset(db, PROJECT_ID, {"api_key": "k"}))
        assert db.assets["arc_summaries"].content_json["book_summary"] == {}

    def test_failure_does_not_raise(self):
        db = _FakeDB(assets=[_FakeAsset("arc_summaries", content_json={
            "arcs": [{"arc_index": 0, "summary": "a"}], "book_summary": {},
        })])
        with patch("app.services.task_service.synthesize_book_summary") as mock_synth:
            mock_synth.side_effect = RuntimeError("LLM down")
            _run(_synthesize_book_summary_asset(db, PROJECT_ID, {"api_key": "k"}))
        assert db.assets["arc_summaries"].content_json["book_summary"] == {}


# ==================== 批量管线接线 + LLM 调用数约束 ====================

def _patch_batch(fake_db, fake_extract_memory, fake_generate_draft=None):
    """对 run_batch_chapters_task 全套 mock，但保留 P3-B 接线钩子为真实实现。"""
    if fake_generate_draft is None:
        async def fake_generate_draft(project, **kwargs):
            return f"第{kwargs['chapter_num']}章草稿"
    fake_task = SimpleNamespace(project_id=PROJECT_ID)
    fake_project = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
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
            "world_state": None,
        }.get(t)),
        load_active_character_cards=AsyncMock(return_value="角色状态文本"),
        generate_chapter_draft=fake_generate_draft,
        extract_chapter_memory=fake_extract_memory,
        extract_world_state_delta=AsyncMock(return_value={"no_changes": True}),
        build_state_summary=AsyncMock(return_value=""),
        check_chapter_consistency=AsyncMock(return_value="CHECK: CONSISTENT"),
        update_character_cards=AsyncMock(return_value={"characters": {}}),
        _save_asset=AsyncMock(),
    )


def _counting_extract_memory(counter):
    async def fake_extract_memory(db, chapter, llm_config):
        counter.append(chapter.chapter_num)
        return {
            "summary": f"第{chapter.chapter_num}章记忆",
            "hook": "h",
            "characters": [],
            "relations_changed": {},
            "foreshadowing_added": [],
            "foreshadowing_touched": [],
            "foreshadowing_recovered": [],
            "subplot_advanced": [],
            "connects_to": "",
        }
    return fake_extract_memory


class TestBatchWiring:
    def test_old_project_no_new_assets_no_llm_overhead(self):
        """旧项目（无 arc_summaries/foreshadowing 资产）：生成行为不变，不新增 LLM 调用。"""
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        mem_calls = []
        draft_calls = []
        with _patch_batch(db, _counting_extract_memory(mem_calls)), \
             patch("app.services.task_service.generate_chapter_draft",
                   side_effect=lambda project, **kw: draft_calls.append(kw["chapter_num"]) or f"草稿{kw['chapter_num']}"), \
             patch("app.services.task_service.build_arc_summary") as mock_build, \
             patch("app.services.task_service.synthesize_book_summary") as mock_synth:
            _run(run_batch_chapters_task(uuid.uuid4()))
            assert mock_build.call_count == 0          # 非 arc 边界，不触发 arc 摘要
            assert mock_synth.call_count == 0          # 无 arc，跳过全书摘要
            assert draft_calls == [1, 2]               # 两章都正常生成
            assert mem_calls == [1, 2]                 # 每章记忆提取一次
        # 旧项目不新增 arc 资产；台账被初始化（空结构），生成行为无变化
        assert "arc_summaries" not in db.assets
        assert db.assets["foreshadowing"].content_json == {"entries": [], "unmatched": []}

    def test_arc_boundary_triggers_arc_summary_and_book_summary(self):
        """arc 边界（ARC_SIZE=2 → 第2章）触发 arc 摘要；全书结束合成 book_summary。"""
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        mem_calls = []
        draft_calls = []
        with patch("app.services.task_service.ARC_SIZE", 2), \
             patch("app.services.task_service.generate_chapter_draft",
                   side_effect=lambda project, **kw: draft_calls.append(kw["chapter_num"]) or f"草稿{kw['chapter_num']}"), \
             patch("app.services.task_service.extract_chapter_memory", _counting_extract_memory(mem_calls)), \
             patch("app.services.task_service.build_arc_summary",
                   return_value={"summary": "arc 摘要", "chapter_range": [1, 2]}) as mock_build, \
             patch("app.services.task_service.synthesize_book_summary",
                   return_value="全书摘要") as mock_synth:
            with _patch_batch(db, _counting_extract_memory(mem_calls)):
                _run(run_batch_chapters_task(uuid.uuid4()))
            assert mock_build.call_count == 1          # 仅边界一章触发
            assert mock_synth.call_count == 1          # 全书结束合成一次
        assert db.assets["arc_summaries"].content_json["arcs"][0]["summary"] == "arc 摘要"
        assert db.assets["arc_summaries"].content_json["book_summary"]["summary"] == "全书摘要"

    def test_llm_call_count_non_boundary_6(self):
        """单章非边界：LLM 调用数 ≤6（现状）。"""
        llm_calls = []

        async def counting_draft(project, **kwargs):
            llm_calls.append("draft")
            return f"草稿{kwargs['chapter_num']}"

        async def counting_state_summary(**kwargs):
            llm_calls.append("state_summary")
            return ""

        async def counting_delta(**kwargs):
            llm_calls.append("delta")
            return {"no_changes": True}

        async def counting_memory(db, chapter, llm_config):
            llm_calls.append("memory")
            return {"summary": "s", "foreshadowing_added": [], "foreshadowing_touched": [],
                    "foreshadowing_recovered": [], "subplot_advanced": []}

        async def counting_check(**kwargs):
            llm_calls.append("consistency")
            return "CHECK: CONSISTENT"

        async def counting_cards(db, project_id, chapter_num, draft_text, **kwargs):
            llm_calls.append("cards")
            return {"characters": {}}

        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        fake_task = SimpleNamespace(project_id=PROJECT_ID)
        fake_project = SimpleNamespace(
            id="00000000-0000-0000-0000-000000000001",
            owner_id="owner-1", genre="", num_chapters=2, word_number=2000, topic="",
            writing_config=None,
        )
        with patch("app.services.task_service.ARC_SIZE", 100), \
             patch.multiple(
                 "app.services.task_service",
                 AsyncSessionLocal=_FakeSessionFactory(db),
                 get_task_by_id=AsyncMock(return_value=fake_task),
                 update_task_status=AsyncMock(),
                 get_project_by_id=AsyncMock(return_value=fake_project),
                 resolve_llm_config=AsyncMock(return_value={"api_key": "test"}),
                 _get_asset_text=AsyncMock(side_effect=lambda db, pid, t: {
                     "architecture": "架构", "directory": "第1章 - 开局\n第2章 - 发展",
                     "world_state": "{\"characters\": {\"张三\": {}}}",
                 }.get(t)),
                 load_active_character_cards=AsyncMock(return_value="角色状态文本"),
                 generate_chapter_draft=counting_draft,
                 build_state_summary=counting_state_summary,
                 extract_world_state_delta=counting_delta,
                 extract_chapter_memory=counting_memory,
                 check_chapter_consistency=counting_check,
                 update_character_cards=counting_cards,
                 _save_asset=AsyncMock(),
             ), \
             patch("app.services.task_service._merge_foreshadowing_ledger", AsyncMock()), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()):
            _run(run_batch_chapters_task(uuid.uuid4()))
        # 两章各 6 类 LLM 调用（state_summary/draft/consistency/cards/delta/memory），非边界不触发 arc 摘要
        assert len(llm_calls) == 12
        assert llm_calls.count("arc_summary") == 0
        assert len(llm_calls) / 2 == 6
        assert len(llm_calls) / 2 <= 6

    def test_llm_call_count_arc_boundary_7(self):
        """单章 arc 边界：LLM 调用数 ≤7（含 arc 摘要，摊薄 1/N）。"""
        llm_calls = []

        async def counting_draft(project, **kwargs):
            llm_calls.append("draft")
            return f"草稿{kwargs['chapter_num']}"

        async def counting_state_summary(**kwargs):
            llm_calls.append("state_summary")
            return ""

        async def counting_delta(**kwargs):
            llm_calls.append("delta")
            return {"no_changes": True}

        async def counting_memory(db, chapter, llm_config):
            llm_calls.append("memory")
            return {"summary": "s", "foreshadowing_added": [], "foreshadowing_touched": [],
                    "foreshadowing_recovered": [], "subplot_advanced": []}

        async def counting_check(**kwargs):
            llm_calls.append("consistency")
            return "CHECK: CONSISTENT"

        async def counting_cards(db, project_id, chapter_num, draft_text, **kwargs):
            llm_calls.append("cards")
            return {"characters": {}}

        async def counting_arc(chapters, llm_config, **kwargs):
            llm_calls.append("arc_summary")
            return {"summary": "arc 摘要", "chapter_range": [1, 2]}

        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        fake_task = SimpleNamespace(project_id=PROJECT_ID)
        fake_project = SimpleNamespace(
            id="00000000-0000-0000-0000-000000000001",
            owner_id="owner-1", genre="", num_chapters=2, word_number=2000, topic="",
            writing_config=None,
        )
        with patch("app.services.task_service.ARC_SIZE", 2), \
             patch.multiple(
                 "app.services.task_service",
                 AsyncSessionLocal=_FakeSessionFactory(db),
                 get_task_by_id=AsyncMock(return_value=fake_task),
                 update_task_status=AsyncMock(),
                 get_project_by_id=AsyncMock(return_value=fake_project),
                 resolve_llm_config=AsyncMock(return_value={"api_key": "test"}),
                 _get_asset_text=AsyncMock(side_effect=lambda db, pid, t: {
                     "architecture": "架构", "directory": "第1章 - 开局\n第2章 - 发展",
                     "world_state": "{\"characters\": {\"张三\": {}}}",
                 }.get(t)),
                 load_active_character_cards=AsyncMock(return_value="角色状态文本"),
                 generate_chapter_draft=counting_draft,
                 build_state_summary=counting_state_summary,
                 extract_world_state_delta=counting_delta,
                 extract_chapter_memory=counting_memory,
                 check_chapter_consistency=counting_check,
                 update_character_cards=counting_cards,
                 _save_asset=AsyncMock(),
             ), \
             patch("app.services.task_service._merge_foreshadowing_ledger", AsyncMock()), \
             patch("app.services.task_service.build_arc_summary", counting_arc), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()):
            _run(run_batch_chapters_task(uuid.uuid4()))
        # 第1章（非边界）6 类 + 第2章（边界）6 类 + 仅边界触发 arc_summary = 13
        assert llm_calls.count("arc_summary") == 1
        assert len(llm_calls) == 13
        # 边界章单章调用数 = 6 常规 + 1 arc = 7 ≤ 7
        assert len([c for c in llm_calls[6:]]) == 7


# ==================== 单章路径 run_chapter_task 接线 ====================

def _patch_single_base(db, chapter_num=1, num_chapters=0):
    """单章路径基础 mock：数据库会话 + 任务/项目查询 + 非 LLM 辅助函数。

    保留 P3-B 真实接线（_build_l2_foreshadowing_context / _merge_foreshadowing_ledger /
    _finalize_arc_summary / _synthesize_book_summary_asset），6 类 LLM 函数由
    _counting_llm_patch 注入，以便精确统计每次 LLM 调用。
    """
    fake_task = SimpleNamespace(project_id=PROJECT_ID, params={"chapter_num": chapter_num})
    fake_project = SimpleNamespace(
        owner_id="owner-1", genre="", num_chapters=num_chapters,
        word_number=2000, topic="", writing_config=None,
    )
    return patch.multiple(
        "app.services.task_service",
        AsyncSessionLocal=_FakeSessionFactory(db),
        get_task_by_id=AsyncMock(return_value=fake_task),
        update_task_status=AsyncMock(),
        get_project_by_id=AsyncMock(return_value=fake_project),
        resolve_llm_config=AsyncMock(return_value={"api_key": "test"}),
        _get_asset_text=AsyncMock(side_effect=lambda db, pid, t: {
            "architecture": "架构文本",
            "directory": "第1章 - 开局\n第2章 - 发展",
            "world_state": '{"characters": {"张三": {}}}',
        }.get(t)),
        load_active_character_cards=AsyncMock(return_value="角色状态文本"),
        _save_asset=AsyncMock(),
    )


def _counting_llm_patch(llm_calls):
    """单章 6 类常规 LLM 调用的 counting 函数（与批量路径同名约定，逐次记录）。"""
    async def counting_draft(project, **kwargs):
        llm_calls.append("draft")
        return f"草稿{kwargs['chapter_num']}"

    async def counting_state_summary(**kwargs):
        llm_calls.append("state_summary")
        return ""

    async def counting_delta(**kwargs):
        llm_calls.append("delta")
        return {"no_changes": True}

    async def counting_memory(db, chapter, llm_config):
        llm_calls.append("memory")
        return {"summary": "s", "foreshadowing_added": [], "foreshadowing_touched": [],
                "foreshadowing_recovered": [], "subplot_advanced": []}

    async def counting_check(**kwargs):
        llm_calls.append("consistency")
        return "CHECK: CONSISTENT"

    async def counting_cards(db, project_id, chapter_num, draft_text, **kwargs):
        llm_calls.append("cards")
        return {"characters": {}}

    return patch.multiple(
        "app.services.task_service",
        generate_chapter_draft=counting_draft,
        build_state_summary=counting_state_summary,
        extract_world_state_delta=counting_delta,
        extract_chapter_memory=counting_memory,
        check_chapter_consistency=counting_check,
        update_character_cards=counting_cards,
    )


class TestSingleChapterWiring:
    """单章路径 run_chapter_task：P3-B 接线 + LLM 调用数约束（此前零覆盖）。"""

    def test_single_non_boundary_llm_le_6(self):
        """单章非边界：6 类常规 LLM 调用，不触发 arc 摘要 / 全书摘要。"""
        llm_calls = []
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with _patch_single_base(db, chapter_num=1, num_chapters=0), \
             _counting_llm_patch(llm_calls), \
             patch("app.services.task_service.ARC_SIZE", 100), \
             patch("app.services.task_service.build_arc_summary", AsyncMock()) as mock_arc, \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()) as mock_book:
            _run(run_chapter_task(uuid.uuid4()))
        assert len(llm_calls) == 6
        assert llm_calls.count("arc_summary") == 0
        mock_arc.assert_not_called()
        mock_book.assert_not_called()

    def test_single_arc_boundary_llm_le_7(self):
        """单章 arc 边界（ARC_SIZE=2 → 第2章）：6 常规 + 1 arc = 7，摊薄 1/N。"""
        llm_calls = []
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])

        async def counting_arc(chapters, llm_config, **kwargs):
            llm_calls.append("arc_summary")
            return {"summary": "arc 摘要", "chapter_range": [1, 2]}

        with _patch_single_base(db, chapter_num=2, num_chapters=0), \
             _counting_llm_patch(llm_calls), \
             patch("app.services.task_service.ARC_SIZE", 2), \
             patch("app.services.task_service.build_arc_summary", counting_arc), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()):
            _run(run_chapter_task(uuid.uuid4()))
        assert llm_calls.count("arc_summary") == 1
        assert len(llm_calls) == 7
        # arc 摘要已冻结写入资产
        arcs = db.assets["arc_summaries"].content_json["arcs"]
        assert arcs[0]["arc_index"] == 0
        assert arcs[0]["chapter_range"] == [1, 2]

    def test_single_last_chapter_synthesizes_book_summary(self):
        """单章写到全书最后一章（chapter_num == num_chapters）→ 合成一次全书摘要（L3，摊薄 1/N）。"""
        llm_calls = []
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with _patch_single_base(db, chapter_num=2, num_chapters=2), \
             _counting_llm_patch(llm_calls), \
             patch("app.services.task_service.ARC_SIZE", 100), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()) as mock_book:
            _run(run_chapter_task(uuid.uuid4()))
        mock_book.assert_called_once()          # 摊薄 1/N：最后一章仅一次
        assert len(llm_calls) == 6              # book 合成独立于每章预算，未占用 6 次

    def test_single_last_chapter_num_chapters_zero_skips(self):
        """num_chapters 未设（0/None）→ 不合成全书摘要（旧项目不写 L3）。"""
        llm_calls = []
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])
        with _patch_single_base(db, chapter_num=2, num_chapters=0), \
             _counting_llm_patch(llm_calls), \
             patch("app.services.task_service.ARC_SIZE", 100), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()) as mock_book:
            _run(run_chapter_task(uuid.uuid4()))
        mock_book.assert_not_called()

    def test_single_old_project_no_new_llm(self):
        """旧项目（无 arc/foreshadowing 资产）：行为不变，LLM 调用数不变，台账初始化为空结构。"""
        llm_calls = []
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1")])
        with _patch_single_base(db, chapter_num=1, num_chapters=0), \
             _counting_llm_patch(llm_calls), \
             patch("app.services.task_service.ARC_SIZE", 100), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()):
            _run(run_chapter_task(uuid.uuid4()))
        assert len(llm_calls) == 6
        assert "arc_summaries" not in db.assets
        # 台账首章初始化为空结构（旧项目兼容：不破坏生成，也不新增 LLM 调用）
        assert db.assets["foreshadowing"].content_json == {"entries": [], "unmatched": []}

    def test_single_last_boundary_both_extra(self):
        """最后一章恰为 arc 边界：arc 摘要 1 次 + 全书摘要 1 次（各自摊薄 1/N，重叠不重复）。"""
        llm_calls = []
        db = _FakeDB(chapters=[_mk_chapter(1, "大纲1"), _mk_chapter(2, "大纲2")])

        async def counting_arc(chapters, llm_config, **kwargs):
            llm_calls.append("arc_summary")
            return {"summary": "arc 摘要", "chapter_range": [1, 2]}

        with _patch_single_base(db, chapter_num=2, num_chapters=2), \
             _counting_llm_patch(llm_calls), \
             patch("app.services.task_service.ARC_SIZE", 2), \
             patch("app.services.task_service.build_arc_summary", counting_arc), \
             patch("app.services.task_service._synthesize_book_summary_asset", AsyncMock()) as mock_book:
            _run(run_chapter_task(uuid.uuid4()))
        assert llm_calls.count("arc_summary") == 1
        assert len(llm_calls) == 7  # 6 常规 + 1 arc；book 单独断言
        mock_book.assert_called_once()
