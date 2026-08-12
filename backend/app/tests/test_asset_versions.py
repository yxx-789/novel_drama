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
        story_shape="final",
        total_chapters_target=None,
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

    async def __aenter__(self):
        # worker 内 `async with AsyncSessionLocal() as db:` 使用
        return self

    async def __aexit__(self, *exc_info):
        return False

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


class TestWorkerWiring:
    """worker 从 task.params 读取 current_content 并传入生成函数；guidance 存原始值。"""

    @patch("app.services.task_service.generate_architecture")
    @patch("app.services.task_service.get_project_by_id")
    @patch("app.services.task_service.resolve_llm_config")
    @patch("app.services.task_service.build_inspiration_guidance")
    @patch("app.services.task_service._save_asset")
    def test_architecture_passes_current_content(self, mock_save, mock_insp, mock_llm, mock_proj, mock_gen):
        from app.services.task_service import run_architecture_task

        project = SimpleNamespace(id="p1", owner_id="u1", topic="t", genre="g",
                                  num_chapters=3, word_number=1500, writing_config=None)
        task = SimpleNamespace(
            id="11111111-1111-1111-1111-111111111111", project_id="22222222-2222-2222-2222-222222222222",
            params={"project_id": "22222222-2222-2222-2222-222222222222", "user_guidance": "侧重人物", "current_content": "现有架构"},
        )
        mock_proj.return_value = project
        mock_llm.return_value = {"api_key": "k"}
        mock_insp.return_value = "灵感内容"
        mock_gen.return_value = ("新架构", "新角色")
        db = FakeDB(results=[task])
        with patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_architecture_task("t1"))
        _, kwargs = mock_gen.call_args
        assert kwargs["current_content"] == "现有架构"
        # 灵感注入仍生效：传给生成函数的 user_guidance 含灵感参考
        assert "灵感内容" in kwargs["user_guidance"]
        # 版本历史记录原始 guidance（未拼接灵感），不含【创作灵感参考】段
        # 注：call_args 是最后一次调用（characters 保存，无 kwargs），须按 asset_type 定位 architecture 调用
        arch_save = next(c for c in mock_save.call_args_list if c.args[2] == "architecture")
        assert arch_save.kwargs["guidance"] == "侧重人物"
        assert "【创作灵感参考】" not in arch_save.kwargs["guidance"]

    @patch("app.services.task_service.generate_directory")
    @patch("app.services.task_service.get_project_by_id")
    @patch("app.services.task_service.resolve_llm_config")
    @patch("app.services.task_service.build_inspiration_guidance")
    @patch("app.services.task_service._save_asset")
    @patch("app.services.task_service._get_asset_text", return_value="现有架构")
    def test_directory_passes_current_content(self, mock_text, mock_save, mock_insp, mock_llm, mock_proj, mock_gen):
        from app.services.task_service import run_directory_task

        project = SimpleNamespace(id="p1", owner_id="u1", topic="t", genre="g",
                                  num_chapters=3, word_number=1500, writing_config=None)
        task = SimpleNamespace(
            id="33333333-3333-3333-3333-333333333333", project_id="44444444-4444-4444-4444-444444444444",
            params={"project_id": "44444444-4444-4444-4444-444444444444", "user_guidance": "节奏加快", "current_content": "现有目录"},
        )
        mock_proj.return_value = project
        mock_llm.return_value = {"api_key": "k"}
        mock_insp.return_value = "灵感内容"
        mock_gen.return_value = ("新目录", [{"chapter_number": 1, "chapter_title": "第1章", "chapter_summary": ""}])
        db = FakeDB(results=[task])
        with patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_directory_task("t1"))
        _, kwargs = mock_gen.call_args
        assert kwargs["current_content"] == "现有目录"
        # 灵感注入仍生效
        assert "灵感内容" in kwargs["user_guidance"]
        # 版本历史记录原始 guidance（未拼接灵感）；按 asset_type 定位 directory 调用
        dir_save = next(c for c in mock_save.call_args_list if c.args[2] == "directory")
        assert dir_save.kwargs["guidance"] == "节奏加快"
        assert "【创作灵感参考】" not in dir_save.kwargs["guidance"]


class TestGenerateRouterGuidance:
    """生成路由：guidance 入 params、超长 400、快照当前内容。"""

    def _make_client(self, fake_db):
        import pytest
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.database import get_db
        from app.routers.dependency import get_current_user
        from app.models.user import User

        async def _fake_get_db():
            yield fake_db

        async def _fake_get_current_user():
            u = User()
            u.id = str(uuid.uuid4())
            return u

        app.dependency_overrides[get_db] = _fake_get_db
        app.dependency_overrides[get_current_user] = _fake_get_current_user
        client = TestClient(app, raise_server_exceptions=False)
        return client

    def _clear_overrides(self, client):
        from app.main import app
        app.dependency_overrides.clear()

    def test_guidance_passed_into_params(self):
        from app.services.task_service import create_task

        captured = {}

        async def _fake_create_task(db, project_id, task_type, params=None):
            captured["params"] = params
            task = SimpleNamespace(
                id="99999999-9999-4999-8999-999999999999", project_id=str(project_id), task_type=task_type,
                status="pending", params=params, progress=0,
                result=None, error_msg=None,
                created_at="2026-08-11T00:00:00+00:00",
                updated_at="2026-08-11T00:00:00+00:00",
            )
            return task

        # 项目存在 + 当前架构快照。
        # get_project_by_id 已被 patch（不消耗 results），第一个真实 execute 来自
        # 路由的 _get_current_asset_text，因此 results 只放快照行（不放 project）。
        # 路径用合法 UUID：路由签名 project_id: uuid.UUID，用 "p1" 会在路径校验处 422。
        project = SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
        db = FakeDB(results=[SimpleNamespace(content_text="现有架构全文")])
        client = self._make_client(db)
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.create_task", side_effect=_fake_create_task), \
             patch("app.routers.generate.run_architecture.delay") as mock_delay:
            res = client.post("/api/projects/11111111-1111-1111-1111-111111111111/generate/architecture", json={"guidance": "侧重群像"})
        self._clear_overrides(client)
        assert res.status_code == 200, res.text
        assert captured["params"]["user_guidance"] == "侧重群像"
        assert captured["params"]["current_content"] == "现有架构全文"
        mock_delay.assert_called_once_with("99999999-9999-4999-8999-999999999999")

    def test_guidance_too_long_returns_400(self):
        from app.routers.generate import GUIDANCE_MAX_LEN

        project = SimpleNamespace(id="11111111-1111-1111-1111-111111111111")
        db = FakeDB(results=[project])
        client = self._make_client(db)
        with patch("app.routers.generate.get_project_by_id", return_value=project):
            res = client.post(
                "/api/projects/11111111-1111-1111-1111-111111111111/generate/architecture",
                json={"guidance": "长" * (GUIDANCE_MAX_LEN + 1)},
            )
        self._clear_overrides(client)
        assert res.status_code == 400, res.text
        assert "优化提示词" in res.json()["detail"]


class TestVersionsRouter:
    """版本列表 + 回滚端点。"""

    _PID = "00000000-0000-0000-0000-000000000001"

    def _make_client(self, db):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.database import get_db
        from app.routers.dependency import get_current_user
        from app.models.user import User

        async def _fake_get_db():
            yield db

        async def _fake_get_current_user():
            u = User()
            u.id = str(uuid.uuid4())
            return u

        app.dependency_overrides[get_db] = _fake_get_db
        app.dependency_overrides[get_current_user] = _fake_get_current_user
        return TestClient(app, raise_server_exceptions=False)

    def _clear_overrides(self):
        from app.main import app
        app.dependency_overrides.clear()

    def test_list_versions_returns_desc(self):
        rows = [
            SimpleNamespace(id="v1", version=2, trigger_type="generate", guidance="优化",
                            created_at="2026-08-11T00:02:00+00:00"),
            SimpleNamespace(id="v2", version=1, trigger_type="manual", guidance=None,
                            created_at="2026-08-11T00:01:00+00:00"),
        ]

        class _RowsResult:
            def scalars(self):
                return SimpleNamespace(all=lambda: rows)

        class _ExecuteDB(FakeDB):
            async def execute(self, stmt):
                return _RowsResult()

        project = SimpleNamespace(id=self._PID)
        client = self._make_client(_ExecuteDB())
        with patch("app.routers.assets.get_project_by_id", return_value=project):
            res = client.get(f"/api/projects/{self._PID}/assets/architecture/versions")
        self._clear_overrides()
        assert res.status_code == 200, res.text
        body = res.json()
        assert [b["version"] for b in body] == [2, 1]
        assert body[0]["trigger_type"] == "generate"

    def test_rollback_returns_404_when_missing(self):
        project = SimpleNamespace(id=self._PID)
        client = self._make_client(FakeDB(results=[]))
        with patch("app.routers.assets.get_project_by_id", return_value=project), \
             patch("app.routers.assets.rollback_asset", return_value=False):
            res = client.post(
                f"/api/projects/{self._PID}/assets/architecture/rollback",
                json={"version": 99},
            )
        self._clear_overrides()
        assert res.status_code == 404, res.text

    def test_rollback_invalid_version_returns_400(self):
        project = SimpleNamespace(id=self._PID)
        client = self._make_client(FakeDB(results=[]))
        with patch("app.routers.assets.get_project_by_id", return_value=project):
            res = client.post(
                f"/api/projects/{self._PID}/assets/architecture/rollback",
                json={"version": "abc"},
            )
        self._clear_overrides()
        assert res.status_code == 400, res.text


class TestArchitectureShapeInstruction:
    def test_architecture_final_injects_closed_loop_instruction(self):
        adapter = CapturingAdapter()
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_architecture(_project(story_shape="final"), llm_config=_LLM))
        seed_prompt = adapter.prompts[0]
        plot_prompt = adapter.prompts[3]
        # Step 1 篇幅行：final 闭环表述
        assert "本书 3 章内完结" in seed_prompt
        # Step 4 指令块：卷目总和 = N、第 N 章结局
        assert "短篇完结" in plot_prompt
        assert "卷目划分总和等于 3" in plot_prompt
        assert "第 3 章为全书结局章" in plot_prompt

    def test_architecture_open_injects_book_map_instruction(self):
        adapter = CapturingAdapter()
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_architecture(
                _project(story_shape="open", total_chapters_target=30), llm_config=_LLM))
        seed_prompt = adapter.prompts[0]
        plot_prompt = adapter.prompts[3]
        # Step 1 篇幅行：连载版图表述
        assert "当前阶段约 3 章" in seed_prompt
        assert "全书规划约 30 章" in seed_prompt
        assert "本书 3 章内完结" not in seed_prompt
        # Step 4 指令块：版图 + 阶段标注 + 第 30 章终点
        assert "连载开篇" in plot_prompt
        assert "前 3 章" in plot_prompt
        assert "续写钩子" in plot_prompt
        assert "第 30 章为全书终点" in plot_prompt

    def test_architecture_open_without_m_renders_gracefully(self):
        adapter = CapturingAdapter()
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_architecture(_project(story_shape="open", total_chapters_target=None), llm_config=_LLM))
        plot_prompt = adapter.prompts[3]
        assert "None" not in plot_prompt
        assert "全书终点章按结局章写法" in plot_prompt
