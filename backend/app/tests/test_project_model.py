# -*- coding: utf-8 -*-
"""story_shape / total_chapters_target 数据模型测试。"""
from sqlalchemy import inspect

from app.models.project import Project


def test_project_has_shape_columns():
    mapper = inspect(Project)
    assert "story_shape" in mapper.columns
    assert "total_chapters_target" in mapper.columns


def test_story_shape_not_null():
    mapper = inspect(Project)
    assert not mapper.columns["story_shape"].nullable


def test_total_chapters_target_nullable():
    mapper = inspect(Project)
    assert mapper.columns["total_chapters_target"].nullable


def test_story_shape_max_length():
    mapper = inspect(Project)
    assert mapper.columns["story_shape"].type.length == 20
