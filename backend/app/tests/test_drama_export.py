# test_drama_export.py
# -*- coding: utf-8 -*-
"""短剧脚本导出接口回归测试。

锁定的 bug：
  - asyncpg 返回的 project_id 是 pgproto.UUID（有 __str__、无 .replace），
    uuid.UUID(pgproto.UUID) 抛 AttributeError → 导出 500。
    修复：调用处统一 uuid.UUID(str(...))。
  - 批量导出的越权防护：所有选中剧集必须属于同一项目且归当前用户。
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.project import DramaEpisode
from app.models.project import Project
from app.models.user import User
from app.routers.dependency import get_current_user
from app.infra.database import get_db


class FakePgUUID:
    """模拟 asyncpg.pgproto.UUID：有 __str__、没有 .replace（触发 uuid.UUID 的 AttributeError）。"""

    def __init__(self, value: str):
        self._value = value

    def __str__(self):
        return self._value


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return _Scalars(self._rows)


class _FakeDB:
    """按查询实体返回剧集列表或项目。"""

    def __init__(self, episodes, project):
        self._episodes = episodes
        self._project = project

    async def execute(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        if entity is DramaEpisode:
            return _FakeResult(self._episodes)
        # Project 查询（get_project_by_id）
        return _FakeResult([self._project] if self._project else [])


def _make_episode(episode_id, project_id, episode_num, script_json=None, status="script_ready"):
    ep = DramaEpisode()
    ep.id = episode_id
    ep.project_id = FakePgUUID(project_id)
    ep.episode_num = episode_num
    ep.title = f"第{episode_num}集"
    ep.source_chapters = "第 1 章"
    ep.outline_json = {"episode_num": episode_num}
    ep.script_json = script_json
    ep.status = status
    return ep


def _make_project(project_id, owner_id):
    p = Project()
    p.id = uuid.UUID(project_id)
    p.owner_id = owner_id
    p.name = "测试项目"
    return p


@pytest.fixture()
def client():
    def _fake_get_db():
        yield _FakeDB([], None)

    def _fake_get_current_user():
        u = User()
        u.id = "51bdf860-5e0c-48b6-92ab-7407c5d68430"
        return u

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_current_user] = _fake_get_current_user
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _override_db(client, episodes, project):
    def _fake_get_db():
        yield _FakeDB(episodes, project)

    app.dependency_overrides[get_db] = _fake_get_db


SCRIPT = {
    "episode_num": 1,
    "title": "测试集",
    "scenes": [
        {
            "scene_num": 1,
            "shots": [
                {
                    "shot_num": 1,
                    "type": "中景",
                    "duration": "3 秒",
                    "visual": "画面",
                    "action": "动作",
                    "camera_movement": "固定",
                    "audio": {"bgm": "BGM", "sfx": ["sfx"]},
                }
            ],
        }
    ],
}


class TestExportSingleEpisode:
    def test_export_json_with_pgproto_project_id(self, client):
        ep = _make_episode(
            "a2ab0e56-705e-4d25-8a1b-cda828b89392",
            "b5010884-1a88-4509-a2c0-86a11ef2aa80",
            1,
            script_json=SCRIPT,
        )
        _override_db(client, [ep], _make_project("b5010884-1a88-4509-a2c0-86a11ef2aa80", "51bdf860-5e0c-48b6-92ab-7407c5d68430"))
        res = client.get(
            "/api/drama/episodes/a2ab0e56-705e-4d25-8a1b-cda828b89392/export?format=json"
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["episode_num"] == 1

    def test_export_without_script_returns_400(self, client):
        ep = _make_episode(
            "a2ab0e56-705e-4d25-8a1b-cda828b89392",
            "b5010884-1a88-4509-a2c0-86a11ef2aa80",
            1,
            script_json=None,
        )
        _override_db(client, [ep], _make_project("b5010884-1a88-4509-a2c0-86a11ef2aa80", "51bdf860-5e0c-48b6-92ab-7407c5d68430"))
        res = client.get(
            "/api/drama/episodes/a2ab0e56-705e-4d25-8a1b-cda828b89392/export?format=json"
        )
        assert res.status_code == 400
        assert "尚未生成脚本" in res.json()["detail"]

    def test_export_missing_episode_returns_404(self, client):
        _override_db(client, [], _make_project("b5010884-1a88-4509-a2c0-86a11ef2aa80", "51bdf860-5e0c-48b6-92ab-7407c5d68430"))
        res = client.get(
            "/api/drama/episodes/a2ab0e56-705e-4d25-8a1b-cda828b89392/export?format=json"
        )
        assert res.status_code == 404


class TestExportBatch:
    def test_batch_same_project_returns_200(self, client):
        ep1 = _make_episode(
            "a2ab0e56-705e-4d25-8a1b-cda828b89392",
            "b5010884-1a88-4509-a2c0-86a11ef2aa80",
            1,
            script_json=SCRIPT,
        )
        _override_db(
            client,
            [ep1],
            _make_project("b5010884-1a88-4509-a2c0-86a11ef2aa80", "51bdf860-5e0c-48b6-92ab-7407c5d68430"),
        )
        res = client.post(
            "/api/drama/episodes/export/batch?format=json",
            json={"episode_ids": ["a2ab0e56-705e-4d25-8a1b-cda828b89392"]},
        )
        assert res.status_code == 200, res.text

    def test_batch_cross_project_returns_400(self, client):
        # 两个剧集分属不同项目 → 越权防护拦截
        ep1 = _make_episode(
            "a2ab0e56-705e-4d25-8a1b-cda828b89392",
            "b5010884-1a88-4509-a2c0-86a11ef2aa80",
            1,
            script_json=SCRIPT,
        )
        ep2 = _make_episode(
            "1307e4e8-3483-4378-8a80-4be174fd196f",
            "99999999-9999-4999-8999-999999999999",
            2,
            script_json=SCRIPT,
        )
        _override_db(
            client,
            [ep1, ep2],
            _make_project("b5010884-1a88-4509-a2c0-86a11ef2aa80", "51bdf860-5e0c-48b6-92ab-7407c5d68430"),
        )
        res = client.post(
            "/api/drama/episodes/export/batch?format=json",
            json={"episode_ids": [ep1.id, ep2.id]},
        )
        assert res.status_code == 400
        assert "不属于同一项目" in res.json()["detail"]

    def test_batch_no_script_returns_400(self, client):
        ep = _make_episode(
            "a2ab0e56-705e-4d25-8a1b-cda828b89392",
            "b5010884-1a88-4509-a2c0-86a11ef2aa80",
            1,
            script_json=None,
        )
        _override_db(
            client,
            [ep],
            _make_project("b5010884-1a88-4509-a2c0-86a11ef2aa80", "51bdf860-5e0c-48b6-92ab-7407c5d68430"),
        )
        res = client.post(
            "/api/drama/episodes/export/batch?format=json",
            json={"episode_ids": ["a2ab0e56-705e-4d25-8a1b-cda828b89392"]},
        )
        assert res.status_code == 400
