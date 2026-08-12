# test_project_router.py
# -*- coding: utf-8 -*-
"""router 层测试：create_new_project 的错误分类契约（I1）+ 故事形态校验（Task 2）。

验证：
  - 无冲突 writing_config → 201 创建成功；
  - 硬冲突 → 400，detail 即服务层给出的冲突文案（明确）；
  - 其它 ValueError → 400，detail 即服务层给出的错误文案；
  - 故事形态 open 缺 M / M 超范围 / M ≤ N → 422（pydantic schema 层）；
  - open 合法 / final 不带 M → 201。
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.routers.dependency import get_current_user
from app.infra.database import get_db


class FakeDB:
    """记录调用并在 commit 时补齐 Project 的默认字段，满足响应序列化。"""

    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            if getattr(obj, "status", None) is None:
                obj.status = "draft"
            now = datetime.now(timezone.utc)
            if getattr(obj, "created_at", None) is None:
                obj.created_at = now
            if getattr(obj, "updated_at", None) is None:
                obj.updated_at = now

    async def refresh(self, obj):
        self.refreshed.append(obj)


async def _fake_get_db():
    yield FakeDB()


async def _fake_get_current_user():
    u = User()
    u.id = str(uuid.uuid4())
    return u


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = _fake_get_current_user
    # 不进 with 上下文，避免 lifespan 触发真实 DB 连接；
    # raise_server_exceptions=False：让未捕获异常以 500 响应返回（而非在测试内重抛）
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_create_project_no_conflict_returns_201(client):
    res = client.post(
        "/api/projects",
        json={"name": "无冲突项目", "story_shape": "final", "writing_config": {"core_genre": "玄幻", "background": "宗门林立"}},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "无冲突项目"
    assert body["writing_config"]["core_genre"] == "玄幻"


def test_create_project_hard_conflict_returns_400_with_message(client):
    res = client.post(
        "/api/projects",
        json={
            "name": "硬冲突项目",
            "story_shape": "final",
            "writing_config": {"cast_scale": "独角戏", "structure": "群像交织"},
        },
    )
    assert res.status_code == 400, res.text
    detail = res.json().get("detail", "")
    assert "写作配置存在冲突" in detail
    assert "独角戏" in detail and "群像交织" in detail


def test_create_project_other_value_error_returns_400(client):
    # 非冲突 ValueError（如内部数据错误）→ 400，detail 即服务层错误文案
    with patch("app.routers.projects.create_project", side_effect=ValueError("内部数据错误")):
        res = client.post(
            "/api/projects",
            json={"name": "内部错误项目", "story_shape": "final", "writing_config": {"core_genre": "玄幻"}},
        )
    assert res.status_code == 400, res.text
    assert "写作配置存在冲突" not in res.text
    assert res.json().get("detail") == "内部数据错误"


# ---------- 故事形态校验（Task 2：open 必填 M / 超范围 / ≤N → 422） ----------
def _create_payload(**overrides):
    base = {
        "name": "形态测试项目",
        "num_chapters": 20,
        "word_number": 2000,
        "story_shape": "final",
    }
    base.update(overrides)
    return base


def test_create_open_missing_m_returns_422(client):
    res = client.post("/api/projects", json=_create_payload(story_shape="open"))
    assert res.status_code == 422, res.text


def test_create_open_m_out_of_range_returns_422(client):
    res = client.post("/api/projects", json=_create_payload(story_shape="open", total_chapters_target=5))
    assert res.status_code == 422, res.text
    res = client.post("/api/projects", json=_create_payload(story_shape="open", total_chapters_target=1001))
    assert res.status_code == 422, res.text


def test_create_open_m_not_greater_than_n_returns_422(client):
    res = client.post("/api/projects", json=_create_payload(story_shape="open", total_chapters_target=20))
    assert res.status_code == 422, res.text


def test_create_final_without_m_returns_201(client):
    res = client.post("/api/projects", json=_create_payload(story_shape="final"))
    assert res.status_code == 201, res.text
    assert res.json()["story_shape"] == "final"
    assert res.json()["total_chapters_target"] is None


def test_create_final_with_m_returns_422(client):
    # final 形态不变量：全书目标总章数必须为 NULL
    res = client.post("/api/projects", json=_create_payload(story_shape="final", total_chapters_target=5))
    assert res.status_code == 422, res.text


def test_create_open_valid_returns_201(client):
    res = client.post("/api/projects", json=_create_payload(story_shape="open", total_chapters_target=30))
    assert res.status_code == 201, res.text
    assert res.json()["total_chapters_target"] == 30
