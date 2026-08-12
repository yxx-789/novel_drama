# test_asset_versions.py
# -*- coding: utf-8 -*-
"""架构/目录 优化重新生成 + 版本历史回滚 单元测试。"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.services.generation_service import generate_architecture, generate_directory, generate_directory_append


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

    def scalars(self):
        # 批量/续写任务用 list(scalars().all()) 读章节列表；row 为 list 时原样返回
        rows = self.row if isinstance(self.row, (list, tuple)) else []
        return SimpleNamespace(all=lambda: list(rows))


class FakeDB:
    """按查询顺序返回预设行的最小 AsyncSession 替身。

    results: 每次 execute 依次 pop 返回；耗尽后返回 None。
    versions: record_asset_version 写入的行参数（供断言）。
    added: add() 的所有对象（供断言 db.add 的章节等）。
    """

    def __init__(self, results=None):
        self.results = list(results or [])
        self.versions = []
        self.added = []
        self.committed = False

    async def __aenter__(self):
        # worker 内 `async with AsyncSessionLocal() as db:` 使用
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def execute(self, stmt):
        return _FakeResult(self.results.pop(0) if self.results else None)

    def add(self, obj):
        self.added.append(obj)
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


class TestContinueWritingRouter:
    """续写路由：前置校验 400/422 + 任务下发。

    与既有路由测试（TestGenerateRouterGuidance）保持同一模式：
    路径用合法 UUID（路由签名 project_id: uuid.UUID，用 "p1" 会在路径校验处 422）。
    """

    _PID = "11111111-1111-1111-1111-111111111111"

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

    def _clear(self, client):
        from app.main import app
        app.dependency_overrides.clear()

    def _task_return(self, chapters):
        # response_model=TaskOut 需要全部字段且 id 为合法 UUID
        return SimpleNamespace(
            id=self._PID,
            project_id=self._PID,
            task_type="continue_writing",
            status="pending",
            params={"project_id": self._PID, "chapters": chapters},
            result=None,
            progress=0,
            error_msg=None,
            created_at="2026-08-11T00:00:00+00:00",
            updated_at="2026-08-11T00:00:00+00:00",
        )

    @patch("app.routers.generate.run_continue_writing")
    @patch("app.routers.generate.create_task")
    def test_continue_router_ok(self, mock_create, mock_delay):
        project = SimpleNamespace(
            id=self._PID, owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project):
            mock_create.return_value = self._task_return(5)
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post(f"/api/projects/{self._PID}/generate/continue-writing", json={"chapters": 5})
            finally:
                self._clear(client)
        assert res.status_code == 200, res.text
        args, kwargs = mock_create.call_args
        assert args[2] == "continue_writing"
        assert kwargs["params"]["chapters"] == 5
        mock_delay.delay.assert_called_once_with(self._PID)

    def test_continue_router_rejects_final_shape(self):
        project = SimpleNamespace(
            id=self._PID, owner_id="u1", story_shape="final", total_chapters_target=None,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.run_continue_writing"):
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post(f"/api/projects/{self._PID}/generate/continue-writing", json={"chapters": 5})
            finally:
                self._clear(client)
        assert res.status_code == 400, res.text

    def test_continue_router_rejects_exceeding_target(self):
        project = SimpleNamespace(
            id=self._PID, owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=28, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.run_continue_writing"):
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post(f"/api/projects/{self._PID}/generate/continue-writing", json={"chapters": 5})
            finally:
                self._clear(client)
        assert res.status_code == 422, res.text

    def test_continue_router_rejects_invalid_k(self):
        project = SimpleNamespace(
            id=self._PID, owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.run_continue_writing"):
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post(f"/api/projects/{self._PID}/generate/continue-writing", json={"chapters": 0})
            finally:
                self._clear(client)
        assert res.status_code == 422, res.text


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


class TestDirectoryShapeInstruction:
    def test_directory_final_injects_final_chapter_requirement(self):
        adapter = CapturingAdapter(_DIRECTORY)
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_directory(
                _project(story_shape="final"), architecture_text="架构", llm_config=_LLM))
        prompt = adapter.prompts[0]
        assert "结局章" in prompt
        assert "伏笔回收清单" in prompt

    def test_directory_open_injects_hooks(self):
        adapter = CapturingAdapter(_DIRECTORY)
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_directory(
                _project(story_shape="open", total_chapters_target=30),
                architecture_text="架构", llm_config=_LLM))
        prompt = adapter.prompts[0]
        assert "阶段性收束" in prompt
        assert "续写钩子" in prompt
        assert "全书终点" in prompt

    def test_directory_open_without_m_renders_gracefully(self):
        adapter = CapturingAdapter(_DIRECTORY)
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_directory(
                _project(story_shape="open", total_chapters_target=None),
                architecture_text="架构", llm_config=_LLM))
        prompt = adapter.prompts[0]
        assert "None" not in prompt
        assert "全书终点章按结局章写法" in prompt


_APPEND = "第4章 - 新篇\n本章简述：承接前文。\n\n第5章 - 推进\n本章简述：埋新线。"


class TestDirectoryAppend:
    def test_append_parses_next_range(self):
        adapter = CapturingAdapter(_APPEND)
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            text, parsed = _run(generate_directory_append(
                _project(story_shape="open", total_chapters_target=30, num_chapters=5),
                architecture_text="架构",
                existing_directory=_DIRECTORY,
                llm_config=_LLM,
            ))
        assert [ch["chapter_number"] for ch in parsed] == [4, 5]
        prompt = adapter.prompts[0]
        assert "追加第 4 章至第 5 章" in prompt
        assert "已有定稿目录（前3章）" in prompt
        # end=5 < M=30 → 阶段收束指令
        assert "阶段收束" in prompt

    def test_append_final_chapter_when_reaching_target(self):
        adapter = CapturingAdapter(_APPEND)
        with patch("app.services.generation_service._make_adapter", return_value=adapter):
            _run(generate_directory_append(
                _project(story_shape="open", total_chapters_target=30, num_chapters=30),
                architecture_text="架构",
                existing_directory=_DIRECTORY,
                llm_config=_LLM,
            ))
        prompt = adapter.prompts[0]
        assert "全书终点" in prompt
        assert "本次续写至第 30 章" in prompt


def _chapter(num, draft=None, status="pending"):
    return SimpleNamespace(
        chapter_num=num, title=f"第{num}章", outline="", draft=draft,
        status=status, project_id="p1",
    )


class TestEnsureChaptersAppendSemantics:
    def test_skip_existing_keeps_draft_chapters_untouched(self):
        from app.services.task_service import _ensure_chapters

        existing = _chapter(1, draft="定稿正文", status="draft_generated")
        db = FakeDB(results=[existing])
        parsed = [
            {"chapter_number": 1, "chapter_title": "新标题", "chapter_summary": "新大纲"},
            {"chapter_number": 2, "chapter_title": "第2章", "chapter_summary": ""},
        ]
        _run(_ensure_chapters(db, "p1", parsed, skip_existing=True))
        # 已存在章节不被覆盖
        assert existing.title == "第1章"
        assert existing.outline == ""
        assert existing.draft == "定稿正文"
        # 新增章节被 add
        added = [o for o in db.added if hasattr(o, "chapter_num")]
        assert [a.chapter_num for a in added] == [2]


class TestBatchIncremental:
    def test_batch_skips_existing_draft(self):
        from app.services.task_service import _batch_generate_drafts

        ch1 = _chapter(1, draft="已有正文", status="draft_generated")
        ch2 = _chapter(2)
        db = FakeDB(results=[])
        project = SimpleNamespace(id="p1", owner_id="u1", genre="玄幻",
                                  num_chapters=2, word_number=1500, writing_config=None,
                                  story_shape="final", total_chapters_target=None)
        with patch("app.services.task_service.generate_chapter_draft") as mock_draft:
            mock_draft.return_value = "新正文"
            _run(_batch_generate_drafts(
                db, "t1", project, {"api_key": "k"}, structure=None,
                architecture_text="架构", directory_text="目录", world_state={},
                template=None, chapter_list=[ch1, ch2], total=2,
            ))
        # 只生成 ch2
        assert mock_draft.call_count == 1
        assert mock_draft.call_args.kwargs["chapter_num"] == 2
        assert ch1.draft == "已有正文"
        assert ch2.draft == "新正文"


def _continue_project(**overrides):
    base = dict(
        id="p1", owner_id="u1", story_shape="open", total_chapters_target=30,
        num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _parsed_1_to_n(n):
    return [
        {"chapter_number": num, "chapter_title": f"第{num}章", "chapter_summary": ""}
        for num in range(1, n + 1)
    ]


def _chapter_rows_1_to_n(n):
    return [
        SimpleNamespace(chapter_num=num, title=f"第{num}章", outline="",
                        draft=None, status="draft", project_id="p1")
        for num in range(1, n + 1)
    ]


class TestContinueWritingTask:
    def test_continue_updates_num_chapters_and_appends(self):
        from app.services.task_service import run_continue_writing_task

        project = _continue_project()
        task = SimpleNamespace(
            id="55555555-5555-5555-5555-555555555555",
            project_id="66666666-6666-6666-6666-666666666666",
            params={"project_id": "66666666-6666-6666-6666-666666666666", "chapters": 5},
        )
        # existing_directory="已有目录" 无解析章节 → existing_count=0 → 追加目录须覆盖 1~25 章
        parsed = _parsed_1_to_n(25)
        # 查询消费顺序：task + 28 个 None（状态/ensure_chapters）+ 章节列表行（scalars）
        chapters = _chapter_rows_1_to_n(25)
        db = FakeDB(results=[task] + [None] * 28 + [chapters])
        with patch("app.services.task_service.get_project_by_id", return_value=project), \
             patch("app.services.task_service.resolve_llm_config", return_value={"api_key": "k"}), \
             patch("app.services.task_service._get_asset_text", side_effect=["架构", "已有目录", "{}"]), \
             patch("app.services.task_service.generate_directory_append",
                   return_value=("追加目录", parsed)) as mock_append, \
             patch("app.services.task_service._save_asset"), \
             patch("app.services.task_service._batch_generate_drafts") as mock_batch, \
             patch("app.services.task_service._synthesize_book_summary_asset"), \
             patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_continue_writing_task("t1"))
        # 1) num_chapters 更新
        assert project.num_chapters == 25
        # 2) 追加目录调用了
        _, kwargs = mock_append.call_args
        assert kwargs["existing_directory"] == "已有目录"
        # 3) 增量正文复用批量循环
        assert mock_batch.call_count == 1

    def test_continue_rejects_exceeding_target(self):
        from app.services.task_service import run_continue_writing_task

        project = _continue_project(num_chapters=28)
        task = SimpleNamespace(
            id="77777777-7777-7777-7777-777777777777",
            project_id="88888888-8888-8888-8888-888888888888",
            params={"project_id": "88888888-8888-8888-8888-888888888888", "chapters": 5},
        )
        # 第二次 get_task_by_id（失败状态落库）需再次返回 task
        db = FakeDB(results=[task, task])
        with patch("app.services.task_service.get_project_by_id", return_value=project), \
             patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_continue_writing_task("t1"))
        # 超界 → 任务失败，num_chapters 不变
        assert project.num_chapters == 28
        assert db.committed  # failed 状态落库

    def test_continue_rejects_non_open_shape(self):
        from app.services.task_service import run_continue_writing_task

        project = _continue_project(story_shape="final")
        task = SimpleNamespace(
            id="99999999-9999-9999-9999-999999999999",
            project_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            params={"project_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "chapters": 5},
        )
        db = FakeDB(results=[task])
        with patch("app.services.task_service.get_project_by_id", return_value=project), \
             patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_continue_writing_task("t1"))
        assert project.num_chapters == 20

    def test_continue_without_target_graceful(self):
        """open + M=None（无全书目标）时续写优雅推进：不校验上限、append 照常调用。"""
        from app.services.task_service import run_continue_writing_task

        project = _continue_project(total_chapters_target=None)
        task = SimpleNamespace(
            id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            project_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
            params={"project_id": "cccccccc-cccc-cccc-cccc-cccccccccccc", "chapters": 5},
        )
        parsed = _parsed_1_to_n(25)
        chapters = _chapter_rows_1_to_n(25)
        db = FakeDB(results=[task] + [None] * 28 + [chapters])
        with patch("app.services.task_service.get_project_by_id", return_value=project), \
             patch("app.services.task_service.resolve_llm_config", return_value={"api_key": "k"}), \
             patch("app.services.task_service._get_asset_text", side_effect=["架构", "", "{}"]), \
             patch("app.services.task_service.generate_directory_append",
                   return_value=("追加目录", parsed)) as mock_append, \
             patch("app.services.task_service._save_asset"), \
             patch("app.services.task_service._batch_generate_drafts"), \
             patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_continue_writing_task("t1"))
        assert project.num_chapters == 25
        assert mock_append.call_count == 1
