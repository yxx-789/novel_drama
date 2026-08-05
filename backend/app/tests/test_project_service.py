# test_project_service.py
# -*- coding: utf-8 -*-
"""create_project 的写作配置校验（Task 2：创建时硬冲突拒绝 / 软警告不阻断）。"""

import asyncio
import uuid

import pytest

from app.generator.block_library import DEFAULT_RECIPES, ConfigHardConflictError
from app.schemas.project import ProjectCreate
from app.services.project_service import create_project


class FakeDB:
    """仅记录调用，不真正落库。"""

    def __init__(self):
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed.append(obj)


def _run_create(config: dict | None):
    db = FakeDB()
    project_in = ProjectCreate(name="测试项目", writing_config=config)
    result = asyncio.run(create_project(db, project_in, uuid.uuid4()))
    return db, result


# ---------- 硬冲突：创建被拒 ----------
def test_create_project_rejects_hard_conflict():
    # 精简卡司 × 群像结构 → 硬冲突，应抛 ConfigHardConflictError（ValueError 子类）且不触碰 DB
    db = FakeDB()
    project_in = ProjectCreate(
        name="冲突项目",
        writing_config={"cast_scale": "独角戏", "structure": "群像交织"},
    )
    with pytest.raises(ConfigHardConflictError) as excinfo:
        asyncio.run(create_project(db, project_in, uuid.uuid4()))
    assert isinstance(excinfo.value, ValueError), "ConfigHardConflictError 应是 ValueError 子类"
    assert "写作配置存在冲突" in str(excinfo.value)
    assert "独角戏" in str(excinfo.value) and "群像交织" in str(excinfo.value)
    assert db.added == [], "硬冲突时不应创建项目"


def test_create_project_rejects_genre_x_background_hard():
    # 历史 × 都市霓虹（现代系）→ 硬冲突
    db = FakeDB()
    project_in = ProjectCreate(
        name="历史都市",
        writing_config={"core_genre": "历史", "background": "都市霓虹"},
    )
    with pytest.raises(ConfigHardConflictError) as excinfo:
        asyncio.run(create_project(db, project_in, uuid.uuid4()))
    assert "历史" in str(excinfo.value) and "都市霓虹" in str(excinfo.value)
    assert db.added == []


# ---------- 软警告：不阻断 ----------
def test_create_project_soft_warnings_do_not_block():
    # 罕见融合（仙侠×末世废土）是软警告，应正常创建并写回 internal_flavor
    db, result = _run_create({"core_genre": "仙侠", "background": "末世废土"})
    assert db.committed is True
    assert result is not None
    assert result.writing_config["core_genre"] == "仙侠"
    assert isinstance(result.writing_config.get("internal_flavor"), list)


# ---------- 无冲突：正常创建 ----------
def test_create_project_clean_config_creates():
    db, result = _run_create(DEFAULT_RECIPES["玄幻"])
    assert db.committed is True
    assert db.added, "无冲突配置应创建项目"
    assert result.writing_config["core_genre"] == "玄幻"
    assert isinstance(result.writing_config.get("internal_flavor"), list)


def test_create_project_without_writing_config_creates():
    # 旧项目/未填配置：跳过校验，正常创建
    db, result = _run_create(None)
    assert db.committed is True
    assert result.writing_config is None


def test_create_project_empty_writing_config_creates():
    # 空 dict 为 falsy，按既有逻辑与未填配置一致（config=None），不崩溃
    db, result = _run_create({})
    assert db.committed is True
    assert result.writing_config is None


# ---------- plot_direction 参与软警告（不阻断） ----------
def test_create_project_plot_direction_soft_warning_does_not_block():
    # plot_direction 是用户输入，剧情走向×设定 只报软警告，不阻断创建
    db, result = _run_create(
        {
            "background": "星际远征",
            "plot_direction": "主角在现代都市的职场一路逆袭",
        }
    )
    assert db.committed is True
    assert result is not None
