# 故事形态（短篇完结 / 连载开篇）与续写闭环 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在创建项目时前置收敛故事形态（`story_shape` = final 短篇完结 / open 连载开篇 + `total_chapters_target` 全书目标 M），并让架构/目录生成按形态产出、补齐 continue_writing 续写闭环（追加目录 + 增量正文）。

**Architecture:** 数据模型加两列（`story_shape` NOT NULL + `total_chapters_target` INTEGER NULL），迁移回填存量 `open/NULL`。生成链路（architecture/directory）从 project 读取形态并注入两处 prompt 指令块；新增 `continue_writing` 任务类型，一个 worker 任务串行执行：更新 `num_chapters` → 追加目录（`append_directory_prompt`，`_ensure_chapters` 追加语义跳过已有）→ 增量正文（复用批量正文循环，已有 draft 章节跳过）。前端：创建表单形态单选必选、设置页形态可改（M 锁定）、目录 tab 续写入口。

**Tech Stack:** FastAPI + async SQLAlchemy + Alembic + Celery（backend）；Vite + React 18 + TypeScript + TanStack Query（frontend）；pytest（backend 测试）。

## Global Constraints

- `story_shape` 取值仅 `'final'` / `'open'`；创建必填（缺失 → 422）。
- `total_chapters_target`（M）：open 必填；10 ≤ M ≤ 1000 且 M > num_chapters（违反 → 422）；**创建后不可修改**（后端 400 + 前端禁用）；final 为 NULL。
- `story_shape` 修改规则：`open→final` 自动清空 M；`final→open` 必须补传 M；修改只影响后续新生成内容。
- 续写前置校验：`project.story_shape == 'open'`；若 M 存在则 `num_chapters + k ≤ M`，且 k ≥ 1。
- 续写任务串行执行：更新 num_chapters → 追加目录（`_ensure_chapters(skip_existing=True)`，已存在章节跳过不动）→ 增量正文（已有 draft 章节跳过）。
- 正文批量生成改为增量语义：只生成未完成章节（`draft` 为空或 status 非 `draft_generated`/`done`）。
- 后端路由更新是 **PUT**（非 PATCH）：`backend/app/routers/projects.py:175`。
- 现有 `ProjectCreate(...)` 调用（测试与前端）必须补 `story_shape`。
- 不实现：正文第 M 章特殊分支（YAGNI）、`architecture_consistency_prompt` 启用（死代码）、M 中途修改（设计禁止）。
- 文档同步：`docs/DATA_MODEL.md`、`docs/API_SPEC.md`、`docs/CHANGELOG.md`、`docs/ARCHITECTURE.md`。

---

### Task 1: 数据模型 + Alembic 迁移 + 存量回填

**Files:**
- Modify: `backend/app/models/project.py:9-22`（Project 类）
- Create: `backend/alembic/versions/<new>_add_story_shape_columns.py`
- Test: `backend/app/tests/test_project_model.py`（新建）

**Interfaces:**
- Consumes: 现有 Project 模型（`backend/app/models/project.py`）、迁移链 head 为 `a1b2c3d4e5f6`（`down_revision` 指向它）。
- Produces: `Project.story_shape: str`（`String(20)`, nullable=False）、`Project.total_chapters_target: int | None`（`Integer`, nullable=True）；迁移文件 `down_revision='a1b2c3d4e5f6'`。

- [ ] **Step 1: 写失败测试**

创建 `backend/app/tests/test_project_model.py`：

```python
# -*- coding: utf-8 -*-
"""story_shape / total_chapters_target 数据模型测试。"""
import pytest
from sqlalchemy import Column, Integer, String, inspect

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_project_model.py -v`
Expected: FAIL — `story_shape` 列不存在。

- [ ] **Step 3: 模型加列**

在 `backend/app/models/project.py` 的 Project 类（`num_chapters` / `word_number` 附近）加：

```python
    story_shape: Mapped[str] = mapped_column(String(20), nullable=False)
    total_chapters_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

（确认该文件顶部已 import `Integer`；若无则补 `from sqlalchemy import Integer, String`。）

- [ ] **Step 4: 生成 Alembic 迁移**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/alembic revision -m "add story shape columns" --autogenerate`
然后编辑生成的迁移文件，确保与以下一致（**autogenerate 可能不生成 server_default，必须手工核对**）：

```python
"""add story shape columns

Revision ID: <autogen>
Revises: a1b2c3d4e5f6
Create Date: <autogen>
"""
from alembic import op
import sqlalchemy as sa

revision: str = '<autogen>'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 存量项目回填 story_shape='open'（现有项目已生成 500 章级架构，天然连载形态）、M=NULL
    op.add_column(
        "projects",
        sa.Column("story_shape", sa.String(20), nullable=False, server_default="open"),
    )
    op.add_column(
        "projects",
        sa.Column("total_chapters_target", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "total_chapters_target")
    op.drop_column("projects", "story_shape")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_project_model.py -v`
Expected: PASS（4 passed）。

- [ ] **Step 6: 本地 PG 验证迁移可执行（回填正确性）**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/alembic upgrade head && .venv/bin/python -c "import asyncio; from sqlalchemy import text; from app.infra.database import engine; ..."` —— 或直接连 PG 验证：
`psql postgresql://postgres:postgres@localhost:5433/ai_novel_studio -c "select story_shape, total_chapters_target from projects limit 5;"`，存量行 story_shape 应为 `open`、M 为 NULL。

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/project.py backend/alembic/versions/<new>.py backend/app/tests/test_project_model.py
git commit -m "feat: projects 表新增 story_shape/total_chapters_target（存量回填 open）"
```

---

### Task 2: Schemas + 创建/更新 API 校验（422 / 400）

**Files:**
- Modify: `backend/app/schemas/project.py:7-33`
- Modify: `backend/app/services/project_service.py:18-59`（create_project）、`86-96`（update_project）
- Modify: `backend/app/routers/projects.py:35-51`（POST 错误处理）、`175-189`（PUT 错误处理）
- Test: `backend/app/tests/test_project_router.py`、`backend/app/tests/test_project_service.py`

**Interfaces:**
- Consumes: Task 1 的 `Project.story_shape` / `Project.total_chapters_target` 列。
- Produces:
  - `ProjectCreate` 新增必填 `story_shape: str` 与可选 `total_chapters_target: int | None`，open 校验在 pydantic `model_validator(mode="after")` 中完成（违规 → 422）。
  - `ProjectUpdate` 新增 `story_shape: str | None = None`、`total_chapters_target: int | None = None`。
  - `update_project` 签名不变；违反锁定/形态规则时抛 `ValueError`，PUT 路由捕获转 400。
  - `ProjectOut` 经 `from_attributes` 输出两列（继承 ProjectBase 自动带上）。

- [ ] **Step 1: 写失败测试（追加到 test_project_router.py）**

```python
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


def test_create_open_valid_returns_201(client):
    res = client.post("/api/projects", json=_create_payload(story_shape="open", total_chapters_target=30))
    assert res.status_code == 201, res.text
    assert res.json()["total_chapters_target"] == 30
```

**同时**：现有 `test_create_project_no_conflict_returns_201` 的请求体缺 `story_shape`，补上 `"story_shape": "final"`（否则该测试 422）。

- [ ] **Step 2: 写失败测试（追加到 test_project_service.py，PUT 锁定/转换规则）**

```python
from app.schemas.project import ProjectUpdate


def _run_update(project, update_in):
    db = FakeDB()
    result = asyncio.run(update_project(db, project, update_in))
    return db, result


def test_update_rejects_changing_m():
    project = SimpleNamespace(
        name="p", story_shape="open", total_chapters_target=30, num_chapters=20,
        word_number=1500, topic=None, genre=None, status="draft",
        writing_config=None, owner_id="u1", id="p1",
    )
    with pytest.raises(ValueError, match="不可修改"):
        _run_update(project, ProjectUpdate(total_chapters_target=99))


def test_update_open_to_final_clears_m():
    project = SimpleNamespace(
        name="p", story_shape="open", total_chapters_target=30, num_chapters=20,
        word_number=1500, topic=None, genre=None, status="draft",
        writing_config=None, owner_id="u1", id="p1",
    )
    _, result = _run_update(project, ProjectUpdate(story_shape="final"))
    assert result.story_shape == "final"
    assert result.total_chapters_target is None


def test_update_final_to_open_requires_m():
    project = SimpleNamespace(
        name="p", story_shape="final", total_chapters_target=None, num_chapters=20,
        word_number=1500, topic=None, genre=None, status="draft",
        writing_config=None, owner_id="u1", id="p1",
    )
    with pytest.raises(ValueError, match="全书目标总章数"):
        _run_update(project, ProjectUpdate(story_shape="open"))


def test_update_final_to_open_with_m_ok():
    project = SimpleNamespace(
        name="p", story_shape="final", total_chapters_target=None, num_chapters=20,
        word_number=1500, topic=None, genre=None, status="draft",
        writing_config=None, owner_id="u1", id="p1",
    )
    _, result = _run_update(project, ProjectUpdate(story_shape="open", total_chapters_target=40))
    assert result.story_shape == "open"
    assert result.total_chapters_target == 40
```

（该文件顶部需补 `from types import SimpleNamespace`、`import pytest`，并确认 `update_project` 已 import。若 FakeDB 已有定义，检查是否带 `commit`/`refresh`；本文件已有 FakeDB（含 commit/refresh）。）

- [ ] **Step 3: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_project_router.py app/tests/test_project_service.py -v`
Expected: FAIL — schema 无 `story_shape` 字段（pydantic 报 extra/校验错误）。

- [ ] **Step 4: Schemas 实现**

`backend/app/schemas/project.py` 改为：

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

SHAPE_VALUES = ("final", "open")


class ProjectBase(BaseModel):
    name: str
    topic: str | None = None
    genre: str | None = None
    num_chapters: int = 0
    word_number: int = 0
    writing_config: dict | None = None
    story_shape: str


class ProjectCreate(ProjectBase):
    total_chapters_target: int | None = None

    @model_validator(mode="after")
    def _validate_shape(self):
        if self.story_shape not in SHAPE_VALUES:
            raise ValueError("故事形态取值非法：final（短篇完结）/ open（连载开篇）")
        if self.story_shape == "open":
            m = self.total_chapters_target
            if m is None:
                raise ValueError("连载开篇必须提供全书目标总章数 total_chapters_target")
            if not (10 <= m <= 1000):
                raise ValueError("全书目标总章数需在 10~1000 之间")
            if m <= self.num_chapters:
                raise ValueError("全书目标总章数必须大于当前章节数")
        return self


class ProjectUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    genre: str | None = None
    num_chapters: int | None = None
    word_number: int | None = None
    status: str | None = None
    writing_config: dict | None = None
    story_shape: str | None = None
    total_chapters_target: int | None = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    total_chapters_target: int | None = None
```

- [ ] **Step 5: service 层实现**

`backend/app/services/project_service.py`：

create_project 的 `Project(...)` 构造补两字段（在 `num_chapters`/`word_number` 之后）：

```python
        story_shape=project_in.story_shape,
        total_chapters_target=project_in.total_chapters_target,
```

update_project 整体替换为：

```python
async def update_project(
    db: AsyncSession,
    project: Project,
    project_in: ProjectUpdate,
) -> Project:
    update_data = project_in.model_dump(exclude_unset=True)

    # 全书目标章数创建后不可修改：已锁定 M 的项目，传入了不同的 M → 拒绝
    if "total_chapters_target" in update_data:
        new_m = update_data["total_chapters_target"]
        if project.total_chapters_target is not None and new_m != project.total_chapters_target:
            raise ValueError("全书目标章数创建后不可修改")
        if new_m is not None and not (10 <= new_m <= 1000):
            raise ValueError("全书目标总章数需在 10~1000 之间")

    # 形态切换规则：open→final 自动清空 M；final→open 必须补传 M
    new_shape = update_data.get("story_shape")
    if new_shape is not None and new_shape != project.story_shape:
        if new_shape not in ("final", "open"):
            raise ValueError("故事形态取值非法：final / open")
        if new_shape == "final":
            update_data["total_chapters_target"] = None
        elif project.story_shape == "final":
            if not update_data.get("total_chapters_target"):
                raise ValueError("切换为连载开篇时必须提供全书目标总章数")

    for field, value in update_data.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project
```

- [ ] **Step 6: 路由错误处理**

`backend/app/routers/projects.py`：

1. `create_new_project` 的 `except ConfigHardConflictError` 后补一个 `except ValueError` 分支转 400（pydantic 的形态校验已在 schema 层返回 422；service 层防御性 ValueError 也按 400 处理，与既有风格一致）：

```python
    except ConfigHardConflictError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

2. `update_existing_project`（PUT）包 try/except：

```python
    try:
        updated = await update_project(db, project, project_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return updated
```

- [ ] **Step 7: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_project_router.py app/tests/test_project_service.py -v`
Expected: PASS（含新增用例与更新后的既有用例）。

- [ ] **Step 8: 提交**

```bash
git add backend/app/schemas/project.py backend/app/services/project_service.py backend/app/routers/projects.py backend/app/tests/test_project_router.py backend/app/tests/test_project_service.py
git commit -m "feat: 项目创建/更新按故事形态校验（open 必填 M、M 锁定不可改）"
```

---

### Task 3: 架构生成形态指令（Step 1 篇幅 + Step 4 情节架构指令块）

**Files:**
- Modify: `backend/app/generator/prompts.py:9-20`（core_seed_prompt 篇幅行）、`187-210`（plot_architecture_prompt）
- Modify: `backend/app/services/generation_service.py:124-224`（`_scope_statement` / `_architecture_shape_instruction` / `generate_architecture`）
- Test: `backend/app/tests/test_asset_versions.py`（追加断言类 + 更新 `_project` helper）

**Interfaces:**
- Consumes: Task 1 的 `project.story_shape` / `project.total_chapters_target`。
- Produces:
  - `_scope_statement(project: Project) -> str` — 核心种子篇幅行。
  - `_architecture_shape_instruction(project: Project) -> str` — 情节架构形态指令块。
  - `generate_architecture` 的 Step 1 模板变量 `scope_statement`、Step 4 模板变量 `shape_instruction`。

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py）**

更新 `_project` helper 加默认形态字段：

```python
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
```

追加测试类：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py::TestArchitectureShapeInstruction -v`
Expected: FAIL — prompt 中无形态指令段。

- [ ] **Step 3: prompts 模板改造**

`backend/app/generator/prompts.py`：

1. `core_seed_prompt` 篇幅行（现第 13 行）`篇幅：约{number_of_chapters}章（每章{word_number}字）` 替换为：

```
篇幅：{scope_statement}
```

2. `plot_architecture_prompt` 的"请围绕上述元素设计整部小说的情节架构，注意："后插入一行占位：

```
请围绕上述元素设计整部小说的情节架构，注意：
{shape_instruction}
- 剧情推进要有起落节奏，张弛有度，避免平铺直叙。
```

- [ ] **Step 4: generation_service 实现**

`backend/app/services/generation_service.py` 新增两个 helper（放在 `_current_content_section` 附近）：

```python
def _scope_statement(project: Project) -> str:
    """构造核心种子篇幅行：final 闭环 / open 连载版图表述。"""
    n = project.num_chapters or 10
    w = project.word_number or 2000
    if project.story_shape == "open":
        m = project.total_chapters_target
        if m:
            return f"当前阶段约 {n} 章（每章 {w} 字），全书规划约 {m} 章，请按全书规模设计"
        return f"约 {n} 章（每章 {w} 字），后续可按需续写"
    return f"约 {n} 章（每章 {w} 字），本书 {n} 章内完结"


def _architecture_shape_instruction(project: Project) -> str:
    """构造情节架构生成的形态约束指令块。"""
    n = project.num_chapters or 10
    if project.story_shape == "open":
        m = project.total_chapters_target
        m_text = f"（全书规划约 {m} 章）" if m else ""
        return (
            f"【形态约束：连载开篇】\n"
            f"本书为连载开篇，当前阶段为前 {n} 章（全书第一阶段）{m_text}。\n"
            f"- 请按全书规模设计版图：卷目划分总和约 {m if m else '全书'} 章，"
            f"主线按全书长度铺排，不在 {n} 章内强行完结。\n"
            f"- 第 {n} 章为阶段收束点，预留 1-3 个续写钩子（未解之谜 / 新线索 / 暗线推进）。\n"
            f"- 第 {m} 章为全书终点（结局章写法）：主线闭合、伏笔全回收。"
        )
    return (
        f"【形态约束：短篇完结】\n"
        f"本书共 {n} 章，本架构必须在此范围内完整闭环：\n"
        f"- 卷目划分总和等于 {n}。\n"
        f"- 主线在 {n} 章内走完，所有伏笔在 {n} 章内回收。\n"
        f"- 第 {n} 章为全书结局章：情感与剧情双收束。"
    )
```

`generate_architecture` 中：

Step 1（现第 156-166 行）format 改为：

```python
    prompt = core_seed_prompt.format(
        topic=project.topic or "",
        genre=project.genre or "",
        scope_statement=_scope_statement(project),
        writing_context=writing_context,
        creative_intent=creative_intent,
        structure_seed_guidance=guidance["seed"],
        current_content_section=current_section,
    )
```

Step 4（现第 194-203 行）format 补：

```python
    prompt = plot_architecture_prompt.format(
        user_guidance=user_guidance or "",
        core_seed=core_seed,
        character_dynamics=character_dynamics,
        world_building=world_building,
        writing_context=writing_context,
        creative_intent=creative_intent,
        current_content_section=current_section,
        shape_instruction=_architecture_shape_instruction(project),
    )
```

**注意**：改动前先 `grep -rn "core_seed_prompt\|plot_architecture_prompt" backend/app --include="*.py"` 确认无其它 format 调用点（预期只有 generation_service）。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: PASS（新增 2 条 + 既有 current_content 测试全绿）。

- [ ] **Step 6: 提交**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/tests/test_asset_versions.py
git commit -m "feat: 架构生成按故事形态注入篇幅表述与闭环/版图指令"
```

---

### Task 4: 目录生成形态指令（第 N 章结局 / 阶段收束 + 钩子）

**Files:**
- Modify: `backend/app/generator/prompts.py:308-330`（chapter_blueprint_prompt）
- Modify: `backend/app/services/generation_service.py`（`_directory_shape_instruction` + `generate_directory`）
- Test: `backend/app/tests/test_asset_versions.py`（追加断言类）

**Interfaces:**
- Consumes: Task 3 的形态 helper 风格。
- Produces: `_directory_shape_instruction(project: Project, end_num: int | None = None) -> str` — 目录形态指令块（`end_num` 供续写追加时判定阶段收束/全书终点，本任务只用到默认值分支）；`generate_directory` 模板变量 `shape_instruction`。

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py::TestDirectoryShapeInstruction -v`
Expected: FAIL。

- [ ] **Step 3: prompts 模板改造**

`chapter_blueprint_prompt` 中 `设计{number_of_chapters}章的节奏分布：` 后插入占位：

```
设计{number_of_chapters}章的节奏分布：
{shape_instruction}
{structure_blueprint_guidance}
```

- [ ] **Step 4: generation_service 实现**

```python
def _directory_shape_instruction(project: Project, end_num: int | None = None) -> str:
    """构造目录生成的形态约束指令块。

    end_num 为本次生成的最后一章（续写追加时传入）：open 模式下
    end_num >= M 按全书终点（结局章）设计，否则阶段收束 + 留钩子。
    """
    n = project.num_chapters or 10
    if project.story_shape == "open":
        m = project.total_chapters_target
        if end_num and m and end_num >= m:
            return (
                f"【形态约束：连载开篇·全书终点】\n"
                f"本次续写至第 {m} 章即全书终点：第 {m} 章按结局章设计，"
                f"主线闭合、情感收束、所有伏笔回收。"
            )
        if end_num:
            return (
                f"【形态约束：连载开篇·阶段收束】\n"
                f"本次续写至第 {end_num} 章，为阶段性收束："
                f"第 {end_num} 章需留下 1-3 个续写钩子（未解之谜 / 新线索 / 暗线推进）。"
            )
        m_text = f"（全书规划约 {m} 章）" if m else ""
        return (
            f"【形态约束：连载开篇】\n"
            f"第 {n} 章为阶段性收束，明确留下 1-3 个续写钩子（未解之谜 / 新线索 / 暗线推进）{m_text}；"
            f"全书终点章（第 {m} 章）按结局章设计。"
        )
    return (
        f"【形态约束：短篇完结】\n"
        f"第 {n} 章必须为结局章——主线闭合、情感收束，并在本章简述中列出伏笔回收清单。"
    )
```

`generate_directory` 的 `chapter_blueprint_prompt.format(...)`（现第 247-255 行）补：

```python
        shape_instruction=_directory_shape_instruction(project),
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/tests/test_asset_versions.py
git commit -m "feat: 目录生成按故事形态注入结局章/阶段收束指令"
```

---

### Task 5: 追加目录模板 + generate_directory_append

**Files:**
- Modify: `backend/app/generator/prompts.py`（新增 `append_directory_prompt`）
- Modify: `backend/app/services/generation_service.py`（新增 `generate_directory_append`）
- Test: `backend/app/tests/test_asset_versions.py`（追加断言类）

**Interfaces:**
- Consumes: Task 4 的 `_directory_shape_instruction(project, end_num)`、`parse_chapter_blueprint`（generation_service 内已有，275 行起）。
- Produces:
  - `append_directory_prompt` — 模板变量：`user_guidance` / `novel_architecture` / `existing_count` / `existing_directory` / `start_num` / `end_num` / `writing_context` / `creative_intent` / `shape_instruction`。
  - `generate_directory_append(project, architecture_text="", existing_directory="", user_guidance="", llm_config=None) -> tuple[str, list[dict]]` — 返回追加目录全文 + 解析出的新章节列表（chapter_number 从 N+1 起）。

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py::TestDirectoryAppend -v`
Expected: FAIL — `generate_directory_append` 不存在。

- [ ] **Step 3: append_directory_prompt 模板**

`backend/app/generator/prompts.py` 末尾追加：

```python
append_directory_prompt = """\
基于以下元素：
- 内容指导：{user_guidance}
- 小说架构：
{novel_architecture}
- 已有定稿目录（前{existing_count}章）：
{existing_directory}

【写作上下文】
{writing_context}

【创作意图】
用户的创作意图，必须严格遵循，冲突时以此为准：
{creative_intent}

请为本书追加第 {start_num} 章至第 {end_num} 章的目录。要求：
- 严格衔接已有目录的节奏曲线与伏笔线索，不要修改、重复或推翻已定稿章节。
- 只输出新增章节，输出格式与已有目录完全一致（"第n章 - [标题]" 起，含本章定位/核心作用/悬念密度/伏笔操作/本章简述）。

{shape_instruction}

仅给出最终文本，不要解释任何内容。
"""
```

- [ ] **Step 4: generate_directory_append 实现**

`backend/app/services/generation_service.py` 中 `generate_directory` 之后新增：

```python
async def generate_directory_append(
    project: Project,
    architecture_text: str = "",
    existing_directory: str = "",
    user_guidance: str = "",
    llm_config: dict | None = None,
) -> tuple[str, list[dict]]:
    """
    续写场景：基于架构版图与已有定稿目录，追加生成第 N+1 ~ N+k 章目录。
    返回：(directory_text, parsed_chapters)，parsed 的 chapter_number 从 N+1 起。
    """
    if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key")):
        raise RuntimeError("LLM API key not configured")

    adapter = _make_adapter(temperature=0.3, llm_config=llm_config)
    writing_context, creative_intent = _prompt_context_for_project(project)

    existing = parse_chapter_blueprint(existing_directory or "")
    existing_count = max((ch["chapter_number"] for ch in existing), default=0)
    start_num = existing_count + 1
    end_num = project.num_chapters or 0
    if start_num > end_num:
        raise RuntimeError("No new chapters to append")

    prompt = append_directory_prompt.format(
        user_guidance=user_guidance or "",
        novel_architecture=architecture_text or "",
        existing_count=existing_count,
        existing_directory=existing_directory or "（暂无）",
        start_num=start_num,
        end_num=end_num,
        writing_context=writing_context,
        creative_intent=creative_intent,
        shape_instruction=_directory_shape_instruction(project, end_num=end_num),
    )
    directory_text = await _invoke_with_retry(adapter, prompt)
    if not directory_text:
        raise RuntimeError("Directory append failed")

    parsed_chapters = parse_chapter_blueprint(directory_text)
    new_nums = [ch["chapter_number"] for ch in parsed_chapters]
    if not new_nums or min(new_nums) != start_num or max(new_nums) != end_num:
        logger.warning(
            f"Directory append parsing mismatch: expected {start_num}~{end_num}, "
            f"got {new_nums}. This may indicate format issues in LLM output."
        )
    logger.info(f"Directory append completed: {len(parsed_chapters)} chapters parsed.")
    return directory_text, parsed_chapters
```

（确认该文件已 import `logger`；若无，顶部补 `logger = logging.getLogger(__name__)`。）

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/tests/test_asset_versions.py
git commit -m "feat: append_directory_prompt + generate_directory_append（续写追加目录）"
```

---

### Task 6: 续写任务服务（_ensure_chapters 追加语义 + 批量增量抽取 + run_continue_writing_task）

**Files:**
- Modify: `backend/app/services/task_service.py`
  - `_ensure_chapters`（304 行）加 `skip_existing` 参数
  - `run_batch_chapters_task`（845 行）重构：循环体抽为 `_batch_generate_drafts`，增量跳过已有 draft
  - 新增 `run_continue_writing_task`
- Test: `backend/app/tests/test_asset_versions.py`（追加测试类）

**Interfaces:**
- Consumes: Task 5 的 `generate_directory_append`；现有 `get_task_by_id`/`update_task_status`/`get_project_by_id`/`resolve_llm_config`/`_get_asset_text`/`_save_asset`/`_synthesize_book_summary_asset`。
- Produces:
  - `_ensure_chapters(db, project_id, parsed_chapters, skip_existing=False)` — `skip_existing=True` 时已存在章节跳过不动。
  - `_batch_generate_drafts(db, task_id, project, llm_config, structure, architecture_text, directory_text, world_state, template, chapter_list, total) -> None` — 串行生成正文，已有 `draft` 且 status 为 `draft_generated`/`done` 的章节跳过；内部负责循环进度更新与结尾统计落库。
  - `run_continue_writing_task(task_id: uuid.UUID) -> None` — 前置校验 → 更新 num_chapters → 追加目录 → 增量正文。

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py）**

```python
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
```

**续写任务测试**（沿用 TestWorkerWiring 的 FakeDB+patch 模式）：

```python
class TestContinueWritingTask:
    def test_continue_updates_num_chapters_and_appends(self):
        from app.services.task_service import run_continue_writing_task

        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        task = SimpleNamespace(
            id="55555555-5555-5555-5555-555555555555",
            project_id="66666666-6666-6666-6666-666666666666",
            params={"project_id": "66666666-6666-6666-6666-666666666666", "chapters": 5},
        )
        db = FakeDB(results=[task])
        with patch("app.services.task_service.get_project_by_id", return_value=project), \
             patch("app.services.task_service.resolve_llm_config", return_value={"api_key": "k"}), \
             patch("app.services.task_service._get_asset_text", side_effect=["架构", "已有目录"]), \
             patch("app.services.task_service.generate_directory_append") as mock_append, \
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

        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=28, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        task = SimpleNamespace(
            id="77777777-7777-7777-7777-777777777777",
            project_id="88888888-8888-8888-8888-888888888888",
            params={"project_id": "88888888-8888-8888-8888-888888888888", "chapters": 5},
        )
        db = FakeDB(results=[task])
        with patch("app.services.task_service.get_project_by_id", return_value=project), \
             patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_continue_writing_task("t1"))
        # 超界 → 任务失败，num_chapters 不变
        assert project.num_chapters == 28
        assert db.committed  # failed 状态落库

    def test_continue_rejects_non_open_shape(self):
        from app.services.task_service import run_continue_writing_task

        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="final", total_chapters_target=None,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py::TestEnsureChaptersAppendSemantics app/tests/test_asset_versions.py::TestBatchIncremental app/tests/test_asset_versions.py::TestContinueWritingTask -v`
Expected: FAIL — `_batch_generate_drafts` / `run_continue_writing_task` 不存在；`_ensure_chapters` 无 `skip_existing` 参数。

- [ ] **Step 3: _ensure_chapters 追加语义**

`backend/app/services/task_service.py` `_ensure_chapters`（304 行）签名与 else 分支改为：

```python
async def _ensure_chapters(
    db: AsyncSession,
    project_id: str,
    parsed_chapters: list[dict],
    skip_existing: bool = False,
) -> None:
    """根据解析的目录，初始化或更新 chapters 表记录。

    skip_existing=True（续写追加场景）：已存在章节跳过不动，保护定稿的标题/大纲。
    """
    from app.models.project import Chapter
    for ch in parsed_chapters:
        num = ch["chapter_number"]
        result = await db.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_num == num,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            chapter = Chapter(
                project_id=project_id,
                chapter_num=num,
                title=ch["chapter_title"] or f"第{num}章",
                outline=ch["chapter_summary"] or "",
                status="draft",
            )
            db.add(chapter)
        elif skip_existing:
            continue
        else:
            # 更新已有记录的标题和摘要
            if ch["chapter_title"]:
                existing.title = ch["chapter_title"]
            if ch["chapter_summary"]:
                existing.outline = ch["chapter_summary"]
    await db.commit()
```

- [ ] **Step 4: 抽取 _batch_generate_drafts + 重构 run_batch_chapters_task**

在 `run_batch_chapters_task`（845 行）之前新增函数，**把原 run_batch_chapters_task 的循环体（现 910-1014 行）与结尾统计（现 1073-1079 行）原样搬入**，仅加增量跳过判断：

```python
async def _batch_generate_drafts(
    db: AsyncSession,
    task_id: uuid.UUID,
    project: Project,
    llm_config: dict,
    structure,
    architecture_text: str,
    directory_text: str,
    world_state: dict,
    template,
    chapter_list: list,
    total: int,
) -> None:
    """串行生成章节正文；已有 draft 的章节跳过（增量语义）。

    批量生成与续写任务共用。负责循环内进度更新与结尾统计/状态落库。
    """
    generated_count = 0
    failed_chapters = []
    for idx, chapter in enumerate(chapter_list):
        chapter_num = chapter.chapter_num
        # 增量语义：已生成的章节跳过（保护定稿正文）
        if chapter.draft and chapter.status in ("draft_generated", "done"):
            logger.info(f"Batch task {task_id}: skip chapter {chapter_num} (draft exists)")
            continue
        logger.info(f"Batch task {task_id}: generating chapter {chapter_num} ({idx + 1}/{total}) ...")
        try:
            # ===== 以下循环体从原 run_batch_chapters_task 原样搬入（previous_draft 起，至 db.commit() + 后台合并/arc 冻结）=====
            previous_draft = None
            previous_summary = ""
            if chapter_num > 1:
                result = await db.execute(
                    select(Chapter).where(
                        Chapter.project_id == str(task.project_id),
                        Chapter.chapter_num == chapter_num - 1,
                    )
                )
                prev_chapter = result.scalar_one_or_none()
                if prev_chapter:
                    previous_draft = prev_chapter.draft
                    previous_summary = _previous_chapter_summary(prev_chapter)

            # 构建 world_state 摘要
            world_state_summary = ""
            if world_state:
                try:
                    parsed = parse_chapter_blueprint(directory_text)
                    current_chapter_info = None
                    for ch in parsed:
                        if ch["chapter_number"] == chapter_num:
                            current_chapter_info = ch
                            break
                    world_state_summary = await build_state_summary(
                        world_state=world_state,
                        target_chapter=chapter_num,
                        chapter_title=current_chapter_info["chapter_title"] if current_chapter_info else "",
                        chapter_summary=current_chapter_info["chapter_summary"] if current_chapter_info else "",
                        llm_config=llm_config,
                        structure=structure,
                    )
                except Exception as e:
                    logger.warning(f"Batch build state summary failed for chapter {chapter_num}: {e}")

            # V3 P3-B：写前追加 L2 上下文（已冻结 arc 摘要 + 伏笔/副线提醒），零新增 LLM 调用
            try:
                l2_context = await _build_l2_foreshadowing_context(
                    db, str(task.project_id), chapter_num, project.genre or ""
                )
                if l2_context:
                    world_state_summary = (
                        f"{world_state_summary}\n\n{l2_context}".strip()
                        if world_state_summary else l2_context
                    )
            except Exception as e:
                logger.warning(f"Batch L2 context build failed for chapter {chapter_num}: {e}")

            # P2-B: 写前只加载出场角色卡（按本章，不再循环外全量加载一次）
            character_state_text = await load_active_character_cards(db, str(task.project_id), chapter_num) or ""

            draft_text = await generate_chapter_draft(
                project,
                chapter_num=chapter_num,
                architecture_text=architecture_text,
                directory_text=directory_text,
                character_state_text=character_state_text,
                previous_chapter_draft=previous_draft,
                previous_chapter_summary=previous_summary,
                world_state_summary=world_state_summary,
                llm_config=llm_config,
            )

            chapter.draft = draft_text
            chapter.status = "draft_generated"

            # 章节生成后一致性检查（非阻塞）
            if character_state_text:
                try:
                    check_result = await check_chapter_consistency(
                        chapter_text=draft_text,
                        character_state_text=character_state_text,
                        previous_chapter_draft=previous_draft,
                        llm_config=llm_config,
                    )
                    if "INCONSISTENT" in check_result.upper():
                        logger.warning(f"Batch chapter {chapter_num} consistency issues detected:\n{check_result}")
                    else:
                        logger.info(f"Batch chapter {chapter_num} consistency check passed.")
                except Exception as e:
                    logger.warning(f"Batch chapter consistency check failed for chapter {chapter_num}: {e}")

            # P2-B: 更新角色卡（结构化档案双通道写回；失败不中断生成，保留旧状态）
            try:
                await update_character_cards(
                    db, str(task.project_id), chapter_num, draft_text, llm_config=llm_config,
                )
            except Exception as e:
                logger.warning(f"Character cards update failed for chapter {chapter_num}: {e}")

            # 提取并更新 world_state（非阻塞）
            try:
                delta = await extract_world_state_delta(
                    chapter_text=draft_text,
                    chapter_number=chapter_num,
                    current_state=world_state,
                    template=template,
                    llm_config=llm_config,
                    structure=structure,
                )
                if not delta.get("no_changes"):
                    world_state = merge_world_state(world_state, delta)
                    await _save_asset(
                        db, str(task.project_id), "world_state",
                        json.dumps(world_state, ensure_ascii=False, indent=2)
                    )
                    logger.info(f"Batch world state updated for chapter {chapter_num}")
            except Exception as e:
                logger.warning(f"Batch world state update failed for chapter {chapter_num}: {e}")

            # 结构化章节记忆提取（非阻塞，失败不中断生成）
            memory = {}
            try:
                memory = await extract_chapter_memory(db, chapter, llm_config)
                if memory and memory.get("summary"):
                    chapter.actual_summary_json = memory
                    logger.info(f"Batch chapter memory extracted for chapter {chapter_num}")
            except Exception as e:
                logger.warning(f"Batch chapter memory extraction failed for chapter {chapter_num}: {e}")

            await db.commit()

            # V3 P3-B：写后台账合并（纯规则）+ arc 边界冻结（失败不中断）
            if memory and memory.get("summary"):
                await _merge_foreshadowing_ledger(
                    db, str(task.project_id), chapter_num, memory, project.genre or ""
                )
            await _finalize_arc_summary(db, str(task.project_id), chapter_num, llm_config)
            # ===== 循环体搬入结束 =====

            generated_count += 1
        except Exception as e:
            logger.exception(f"Batch chapter {chapter_num} generation failed: {e}")
            failed_chapters.append({"chapter_num": chapter_num, "error": str(e)})
            await db.commit()

        progress = 10 + int((idx + 1) / total * 85)
        await update_task_status(
            db, task_id, "running", progress=progress,
            result={
                "current_chapter": chapter_num,
                "completed": generated_count,
                "total": total,
                "failed": len(failed_chapters),
                "failed_chapters": failed_chapters,
            }
        )

    # V3 P3-B：全书写完（循环结束）合成全书摘要（L3）；失败不中断
    try:
        await _synthesize_book_summary_asset(db, str(project.id), llm_config)
    except Exception as e:
        logger.warning(f"Book summary synthesis failed for task {task_id}: {e}")

    if failed_chapters:
        await update_task_status(
            db, task_id, "success", progress=100,
            result={
                "total": total,
                "generated": generated_count,
                "failed_count": len(failed_chapters),
                "failed_chapters": failed_chapters,
            }
        )
        logger.warning(f"Batch chapters task {task_id} completed with failures: {generated_count}/{total}, failed: {failed_chapters}")
    else:
        await update_task_status(
            db, task_id, "success", progress=100,
            result={"total": total, "generated": generated_count}
        )
        logger.info(f"Batch chapters task {task_id} completed: {generated_count}/{total}")
```

`run_batch_chapters_task` 主体重构为（**保留前置数据读取，删除原循环体与结尾**）：

```python
async def run_batch_chapters_task(task_id: uuid.UUID) -> None:
    """后台执行批量章节正文生成任务（串行逐章生成，已有 draft 章节跳过）"""
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            await update_task_status(db, task_id, "running", progress=5)

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")

            llm_config = await resolve_llm_config(str(project.owner_id), db)
            structure = _structure_for_project(project)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")

            directory_text = await _get_asset_text(db, str(task.project_id), "directory")
            if not directory_text:
                raise RuntimeError("Directory not found. Please generate directory first.")

            # 读取 world_state
            world_state_raw = await _get_asset_text(db, str(task.project_id), "world_state")
            world_state: dict = {}
            if world_state_raw:
                try:
                    world_state = json.loads(world_state_raw)
                except Exception:
                    world_state = {}
            template = get_template(project.genre or "")

            # 获取所有需要生成的章节
            from app.models.project import Chapter
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                ).order_by(Chapter.chapter_num)
            )
            chapter_list = list(result.scalars().all())
            total = len(chapter_list)
            if total == 0:
                raise RuntimeError("No chapters found. Please generate directory first.")

            await update_task_status(db, task_id, "running", progress=10)
            await _batch_generate_drafts(
                db, task_id, project, llm_config, structure,
                architecture_text, directory_text, world_state, template, chapter_list, total,
            )
        except Exception as e:
            logger.exception(f"Batch chapters task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass
```

**注意**：`_batch_generate_drafts` 内使用了 `Chapter`（select(Chapter)）——该引用来自循环体原有 import 语句的位置，确保函数内 `from app.models.project import Chapter` 在 `previous_draft` 查询之前可用（原代码中该 import 在 run_batch_chapters_task 顶部 `from app.models.project import Chapter`，搬移后需在函数内保留）。

- [ ] **Step 5: run_continue_writing_task 实现**

`run_batch_chapters_task` 之后新增：

```python
async def run_continue_writing_task(task_id: uuid.UUID) -> None:
    """续写闭环：更新 num_chapters → 追加目录 → 增量正文（一个任务串行执行）。"""
    async with AsyncSessionLocal() as db:
        try:
            task = await get_task_by_id(db, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            project = await get_project_by_id(db, uuid.UUID(str(task.project_id)))
            if not project:
                raise RuntimeError("Project not found")
            if project.story_shape != "open":
                raise RuntimeError("仅连载开篇（open）形态项目可续写")

            k = int((task.params or {}).get("chapters", 0) or 0)
            if k < 1:
                raise RuntimeError("续写章数必须为正整数")
            m = project.total_chapters_target
            if m and project.num_chapters + k > m:
                raise RuntimeError(f"续写后总章数不能超过全书目标 {m} 章")

            await update_task_status(db, task_id, "running", progress=10)

            # 1. 更新全书章数
            project.num_chapters = project.num_chapters + k
            await db.commit()

            llm_config = await resolve_llm_config(str(project.owner_id), db)
            structure = _structure_for_project(project)

            architecture_text = await _get_asset_text(db, str(task.project_id), "architecture")
            if not architecture_text:
                raise RuntimeError("Architecture not found. Please generate architecture first.")
            existing_directory = await _get_asset_text(db, str(task.project_id), "directory")

            # 2. 追加目录（只新增 N+1 ~ N+k 章，不覆盖已有定稿）
            await update_task_status(db, task_id, "running", progress=30)
            directory_text, parsed_chapters = await generate_directory_append(
                project,
                architecture_text=architecture_text,
                existing_directory=existing_directory or "",
                llm_config=llm_config,
            )
            await _save_asset(db, str(task.project_id), "directory", directory_text,
                              trigger_type="generate", guidance="continue_writing")
            await _ensure_chapters(db, str(task.project_id), parsed_chapters, skip_existing=True)

            # 3. 增量正文（已有 draft 章节自动跳过）
            await update_task_status(db, task_id, "running", progress=45)
            world_state_raw = await _get_asset_text(db, str(task.project_id), "world_state")
            world_state: dict = {}
            if world_state_raw:
                try:
                    world_state = json.loads(world_state_raw)
                except Exception:
                    world_state = {}
            template = get_template(project.genre or "")
            from app.models.project import Chapter
            result = await db.execute(
                select(Chapter).where(
                    Chapter.project_id == str(task.project_id),
                ).order_by(Chapter.chapter_num)
            )
            chapter_list = list(result.scalars().all())
            total = len(chapter_list)
            if total == 0:
                raise RuntimeError("No chapters found after directory append.")

            await _batch_generate_drafts(
                db, task_id, project, llm_config, structure,
                architecture_text, directory_text, world_state, template, chapter_list, total,
            )
            logger.info(f"Continue writing task {task_id} completed")
        except Exception as e:
            logger.exception(f"Continue writing task {task_id} failed: {e}")
            try:
                await update_task_status(db, task_id, "failed", error_msg=str(e))
            except Exception:
                pass
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: PASS（新增 5 条 + 既有全绿）。若 `TestBatchIncremental` 中 `structure=None`/`template=None` 触达真实 `build_state_summary`/`extract_world_state_delta`，说明 `world_state={}` 为空时不会调用（循环内 `if world_state:` 保护），无需额外 mock——若报错再按报错点补充 patch。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/task_service.py backend/app/tests/test_asset_versions.py
git commit -m "feat: continue_writing 任务（更新章数 + 追加目录 + 增量正文）"
```

---

### Task 7: worker 接线 + 续写路由

**Files:**
- Modify: `backend/app/worker/tasks.py`
- Modify: `backend/app/routers/generate.py`
- Test: `backend/app/tests/test_asset_versions.py`（追加路由测试）

**Interfaces:**
- Consumes: Task 6 的 `run_continue_writing_task`；`create_task`；`get_project_by_id`。
- Produces: Celery task `run_continue_writing(task_id: str)`；路由 `POST /api/projects/{project_id}/generate/continue-writing`（payload `{"chapters": k}`），前置校验返回 400/422。

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py 的 TestGenerateRouterGuidance 附近）**

```python
class TestContinueWritingRouter:
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

    @patch("app.routers.generate.run_continue_writing")
    @patch("app.services.task_service.create_task")
    def test_continue_router_ok(self, mock_create, mock_delay):
        from app.routers.generate import get_project_by_id as router_get_proj
        import app.routers.generate as gen_mod

        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project):
            mock_create.return_value = SimpleNamespace(id="task1")
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post("/api/projects/p1/generate/continue-writing", json={"chapters": 5})
            finally:
                self._clear(client)
        assert res.status_code == 200, res.text
        _, kwargs = mock_create.call_args
        assert kwargs["task_type"] == "continue_writing"
        assert kwargs["params"]["chapters"] == 5

    def test_continue_router_rejects_final_shape(self):
        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="final", total_chapters_target=None,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.run_continue_writing"):
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post("/api/projects/p1/generate/continue-writing", json={"chapters": 5})
            finally:
                self._clear(client)
        assert res.status_code == 400, res.text

    def test_continue_router_rejects_exceeding_target(self):
        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=28, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.run_continue_writing"):
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post("/api/projects/p1/generate/continue-writing", json={"chapters": 5})
            finally:
                self._clear(client)
        assert res.status_code == 422, res.text

    def test_continue_router_rejects_invalid_k(self):
        project = SimpleNamespace(
            id="p1", owner_id="u1", story_shape="open", total_chapters_target=30,
            num_chapters=20, topic="t", genre="g", word_number=1500, writing_config=None,
        )
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.run_continue_writing"):
            db = FakeDB()
            client = self._make_client(db)
            try:
                res = client.post("/api/projects/p1/generate/continue-writing", json={"chapters": 0})
            finally:
                self._clear(client)
        assert res.status_code == 422, res.text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py::TestContinueWritingRouter -v`
Expected: FAIL — 路由 404（未定义）。

- [ ] **Step 3: worker 接线**

`backend/app/worker/tasks.py`：

1. import 补 `run_continue_writing_task`。
2. 文件末尾追加：

```python
@celery_app.task(bind=True)
def run_continue_writing(self, task_id: str):
    logger.info(f"Celery task [continue_writing] started for task_id={task_id}")
    asyncio.run(_run_with_cleanup(run_continue_writing_task(uuid.UUID(task_id))))
    return {"status": "success"}
```

- [ ] **Step 4: 续写路由**

`backend/app/routers/generate.py`：

1. import 补 `run_continue_writing`。
2. 文件末尾追加：

```python
@router.post("/projects/{project_id}/generate/continue-writing", response_model=TaskOut)
async def trigger_continue_writing_generation(
    project_id: uuid.UUID,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    if project.story_shape != "open":
        raise HTTPException(status_code=400, detail="仅连载开篇（open）形态项目可续写")
    try:
        k = int(payload.get("chapters", 0))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="续写章数必须为正整数")
    if k < 1:
        raise HTTPException(status_code=422, detail="续写章数必须为正整数")
    m = project.total_chapters_target
    if m and project.num_chapters + k > m:
        raise HTTPException(
            status_code=422,
            detail=f"续写后总章数不能超过全书目标 {m} 章（剩余 {m - project.num_chapters} 章）",
        )
    task = await create_task(
        db, project_id, "continue_writing",
        params={"project_id": str(project_id), "chapters": k},
    )
    run_continue_writing.delay(str(task.id))
    return task
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/worker/tasks.py backend/app/routers/generate.py backend/app/tests/test_asset_versions.py
git commit -m "feat: continue_writing worker 接线 + 续写生成路由（前置校验）"
```

---

### Task 8: 前端 API 层

**Files:**
- Modify: `frontend/src/api/project.ts`
- Modify: `frontend/src/api/generate.ts`

**Interfaces:**
- Consumes: Task 2 的 API 契约（story_shape 必填、total_chapters_target、PUT 拒绝改 M）。
- Produces:
  - `Project` 接口加 `story_shape: string`、`total_chapters_target: number | null`
  - `CreateProjectRequest` 加 `story_shape?: string`、`total_chapters_target?: number`
  - `UpdateProjectRequest` 加 `story_shape?: string`
  - `generateContinueWriting(projectId: string, chapters: number): Promise<Task>`

- [ ] **Step 1: 修改 project.ts**

`frontend/src/api/project.ts`：

```ts
export interface Project {
  id: string
  name: string
  topic: string | null
  genre: string | null
  num_chapters: number
  word_number: number
  story_shape: string
  total_chapters_target: number | null
  owner_id: string
  status: string
  created_at: string
  updated_at: string
}

export interface CreateProjectRequest {
  name: string
  topic?: string
  genre?: string
  num_chapters?: number
  word_number?: number
  story_shape?: string
  total_chapters_target?: number
  writing_config?: object
}

export interface UpdateProjectRequest {
  name?: string
  topic?: string
  genre?: string
  num_chapters?: number
  word_number?: number
  story_shape?: string
  status?: string
}
```

- [ ] **Step 2: 修改 generate.ts**

`frontend/src/api/generate.ts` 末尾追加：

```ts
export const generateContinueWriting = async (projectId: string, chapters: number): Promise<Task> => {
  const response = await apiClient.post<Task>(
    `/api/projects/${projectId}/generate/continue-writing`,
    { chapters }
  )
  return response.data
}
```

（确认该文件顶部已有 `import apiClient from './client'` 与 `Task` 类型 import，与既有函数一致。）

- [ ] **Step 3: 验证**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/project.ts frontend/src/api/generate.ts
git commit -m "feat: 前端 API 层支持 story_shape / total_chapters_target / 续写"
```

---

### Task 9: ProjectCreate 表单（形态单选必选 + M 输入）

**Files:**
- Modify: `frontend/src/pages/ProjectCreate.tsx`

**Interfaces:**
- Consumes: Task 8 的 `CreateProjectRequest`。
- Produces: 表单 state `storyShape`（`'final' | 'open' | ''`）、`totalChaptersTarget`（`number | ''`）；提交 payload 带 `story_shape` / `total_chapters_target`；前端校验（形态必选、open 时 M 必填且 10~1000 且 > numChapters）。

- [ ] **Step 1: 加 state（144-145 行 numChapters/wordNumber 附近）**

```tsx
const [storyShape, setStoryShape] = useState<'final' | 'open' | ''>('')
const [totalChaptersTarget, setTotalChaptersTarget] = useState<number | ''>('')
```

- [ ] **Step 2: 提交校验与 payload（353-354 行附近）**

在 handleSubmit 构造 payload 前加校验：

```tsx
if (!storyShape) {
  setError('请选择故事形态（短篇完结 / 连载开篇）')
  return
}
if (storyShape === 'open') {
  const m = Number(totalChaptersTarget)
  if (!totalChaptersTarget || !Number.isInteger(m) || m < 10 || m > 1000) {
    setError('全书目标总章数需为 10~1000 的整数')
    return
  }
  if (m <= numChapters) {
    setError('全书目标总章数必须大于章节数')
    return
  }
}
```

payload 加：

```tsx
story_shape: storyShape || undefined,
total_chapters_target: storyShape === 'open' ? Number(totalChaptersTarget) || undefined : undefined,
```

- [ ] **Step 3: 表单 UI（422-444 行 grid 输入之后新增区块）**

```tsx
<div>
  <label className="block text-sm font-medium text-gray-700">故事形态</label>
  <div className="mt-1 space-y-2">
    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
      <input
        type="radio"
        name="storyShape"
        checked={storyShape === 'final'}
        onChange={() => setStoryShape('final')}
        className="accent-indigo-600"
      />
      <span>短篇完结（{numChapters || 20} 章即全书结局，情节架构在本章数内闭环）</span>
    </label>
    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
      <input
        type="radio"
        name="storyShape"
        checked={storyShape === 'open'}
        onChange={() => setStoryShape('open')}
        className="accent-indigo-600"
      />
      <span>连载开篇（先写 {numChapters || 20} 章看反响，第 {numChapters || 20} 章留钩子，后续可续写）</span>
    </label>
  </div>
</div>
{storyShape === 'open' && (
  <div>
    <label className="block text-sm font-medium text-gray-700">全书目标总章数 M</label>
    <input
      type="number"
      min={10}
      max={1000}
      value={totalChaptersTarget}
      onChange={(e) => setTotalChaptersTarget(e.target.value === '' ? '' : Number(e.target.value))}
      placeholder="例如 60"
      className="mt-1 w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
    />
    <p className="mt-1 text-xs text-amber-600">该数字创建后不可修改，请谨慎填写</p>
  </div>
)}
```

- [ ] **Step 4: 验证**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit && npm run build`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/ProjectCreate.tsx
git commit -m "feat: 创建表单故事形态单选（open 展开全书目标章数 M）"
```

---

### Task 10: OverviewTab 形态设置（形态可改 + M 锁定展示）

**Files:**
- Modify: `frontend/src/pages/ProjectDetail/OverviewTab.tsx`
- Modify: `frontend/src/pages/ProjectDetail/index.tsx`

**Interfaces:**
- Consumes: Task 8 的 `Project.story_shape` / `Project.total_chapters_target`；Task 2 的 PUT 契约（open→final 清 M / final→open 补 M / M 不可改）。
- Produces:
  - `OverviewTab` 新增 props：`storyShape: string`、`setStoryShape: (v: string) => void`、`totalChaptersTarget: number | null`、`setTotalChaptersTarget: (v: number | null) => void`
  - `index.tsx` 持有 state 并同步到 `handleSaveProject` payload。

- [ ] **Step 1: OverviewTab props 扩展**

```tsx
interface OverviewTabProps {
  // ...既有 props
  storyShape: string
  setStoryShape: (v: string) => void
  totalChaptersTarget: number | null
  setTotalChaptersTarget: (v: number | null) => void
}
```

解构处同步加 4 个参数。

- [ ] **Step 2: OverviewTab 编辑区形态 UI**

在编辑表单中（wordNumber 输入之后）加：

```tsx
<div>
  <label className="block text-sm font-medium text-gray-700">故事形态</label>
  <div className="mt-1 space-y-2">
    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
      <input
        type="radio"
        name="storyShapeEdit"
        checked={storyShape === 'final'}
        onChange={() => { setStoryShape('final'); setTotalChaptersTarget(null) }}
        className="accent-indigo-600"
      />
      <span>短篇完结（第 {numChapters} 章即全书结局）</span>
    </label>
    <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
      <input
        type="radio"
        name="storyShapeEdit"
        checked={storyShape === 'open'}
        onChange={() => setStoryShape('open')}
        className="accent-indigo-600"
      />
      <span>连载开篇（第 {numChapters} 章留钩子，后续可续写）</span>
    </label>
  </div>
  {storyShape === 'open' && (
    <div className="mt-2">
      {totalChaptersTarget ? (
        <p className="text-sm text-gray-700">
          全书目标总章数：<span className="font-medium">{totalChaptersTarget}</span> 章
          <span className="ml-2 text-xs text-gray-400">（创建后不可修改）</span>
        </p>
      ) : (
        <div>
          <label className="block text-sm font-medium text-gray-700">全书目标总章数 M</label>
          <input
            type="number"
            min={10}
            max={1000}
            value={totalChaptersTarget ?? ''}
            onChange={(e) => setTotalChaptersTarget(e.target.value === '' ? null : Number(e.target.value))}
            placeholder="10~1000"
            className="mt-1 w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          />
          <p className="mt-1 text-xs text-amber-600">该数字创建后不可修改，请谨慎填写</p>
        </div>
      )}
    </div>
  )}
</div>
```

- [ ] **Step 3: 只读展示区（149 行 num_chapters 附近）**

```tsx
<p className="text-base font-medium text-gray-900">
  {project.story_shape === 'open' ? '连载开篇' : '短篇完结'}
</p>
{project.story_shape === 'open' && project.total_chapters_target && (
  <p className="text-base font-medium text-gray-900">全书目标：{project.total_chapters_target} 章（锁定）</p>
)}
```

- [ ] **Step 4: index.tsx 接线**

1. state 声明（`const [numChapters, setNumChapters] = useState(0)` 附近）：

```tsx
const [storyShape, setStoryShape] = useState<string>('final')
const [totalChaptersTarget, setTotalChaptersTarget] = useState<number | null>(null)
```

2. project 加载同步（149 行 `setNumChapters(project.num_chapters)` 附近）：

```tsx
setStoryShape(project.story_shape || 'final')
setTotalChaptersTarget(project.total_chapters_target ?? null)
```

3. `handleSaveProject` payload（262 行附近）加：

```tsx
story_shape: storyShape,
total_chapters_target: storyShape === 'open' ? totalChaptersTarget : undefined,
```

4. OverviewTab 渲染处传 4 个新 props。

- [ ] **Step 5: 验证**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit && npm run build`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/ProjectDetail/OverviewTab.tsx frontend/src/pages/ProjectDetail/index.tsx
git commit -m "feat: 设置页故事形态可改（open→final 清 M，M 锁定只读展示）"
```

---

### Task 11: DirectoryTab 续写入口 + 任务轮询接线

**Files:**
- Modify: `frontend/src/pages/ProjectDetail/DirectoryTab.tsx`
- Modify: `frontend/src/pages/ProjectDetail/index.tsx`

**Interfaces:**
- Consumes: Task 7 的路由 `POST .../generate/continue-writing`；Task 8 的 `generateContinueWriting`；现有 `pollTask`（`frontend/src/api/task.ts` 或 utils，按既有 handleGenerateDirectory 用法）。
- Produces:
  - `DirectoryTab` 新增 props：`canContinue: boolean`、`totalChaptersTarget: number | null`、`numChapters: number`、`onContinue: (k: number) => void`
  - `index.tsx` `handleContinueWriting(k)` + activeTask 轮询补 `continue_writing` 分支。

- [ ] **Step 1: DirectoryTab props + 续写按钮**

props 扩展：

```tsx
interface DirectoryTabProps {
  // ...既有 props
  canContinue: boolean
  totalChaptersTarget: number | null
  numChapters: number
  onContinue: (k: number) => void
}
```

工具栏（GuidancePanel 附近）加「续写」按钮 + 弹窗：

```tsx
const [showContinue, setShowContinue] = useState(false)
const [continueK, setContinueK] = useState<number>(1)

{canContinue && (
  <>
    <button
      onClick={() => { setContinueK(1); setShowContinue(true) }}
      className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg"
    >
      续写
    </button>
    {showContinue && (
      <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
        <div className="glass-panel p-6 rounded-xl w-96">
          <h3 className="text-base font-medium text-slate-800 mb-3">续写章节</h3>
          <p className="text-sm text-gray-600 mb-3">
            当前已写 {numChapters} 章
            {totalChaptersTarget ? `，全书目标 ${totalChaptersTarget} 章（剩余 ${totalChaptersTarget - numChapters} 章）` : ''}
            。本次续写将追加目录并生成正文。
          </p>
          <label className="block text-sm font-medium text-gray-700 mb-1">续写章数 k</label>
          <input
            type="number"
            min={1}
            max={totalChaptersTarget ? totalChaptersTarget - numChapters : undefined}
            value={continueK}
            onChange={(e) => setContinueK(Number(e.target.value))}
            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          />
          <div className="mt-4 flex justify-end gap-2">
            <button onClick={() => setShowContinue(false)} className="px-4 py-2 text-sm text-gray-600">取消</button>
            <button
              onClick={() => {
                if (continueK < 1) return
                if (totalChaptersTarget && continueK > totalChaptersTarget - numChapters) return
                setShowContinue(false)
                onContinue(continueK)
              }}
              className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg"
            >
              开始续写
            </button>
          </div>
        </div>
      </div>
    )}
  </>
)}
```

- [ ] **Step 2: index.tsx 续写 handler**

`handleGenerateDirectory` 之后加：

```tsx
const handleContinueWriting = async (k: number) => {
  if (!id) return
  setDirectoryGenerating(true)
  try {
    const task = await generateContinueWriting(id, k)
    setError('')
    setActiveTask({ id: task.id, type: 'continue_writing', progress: 0, status: 'pending' })
    pollCleanupRef.current?.()
    pollCleanupRef.current = pollTask(
      task.id,
      async () => {
        queryClient.invalidateQueries({ queryKey: ['asset', id, 'directory'] })
        queryClient.invalidateQueries({ queryKey: ['chapters', id] })
        queryClient.invalidateQueries({ queryKey: ['project', id] })
        setDirectoryGenerating(false)
        setActiveTask(null)
      },
      (msg) => {
        setError(`续写失败: ${msg}`)
        setDirectoryGenerating(false)
        setActiveTask(null)
      },
      (progress, status) => {
        setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
      }
    )
  } catch (err: any) {
    setError(err.response?.data?.detail || '创建续写任务失败')
    setDirectoryGenerating(false)
    setActiveTask(null)
  }
}
```

（import 补 `generateContinueWriting` from `../../api/generate`。）

- [ ] **Step 3: 轮询分支（179-238 行）**

1. `setActiveTask` 状态分支补：

```tsx
} else if (runningTask.task_type === 'continue_writing') {
  setActiveTask({ id: runningTask.id, type: 'continue_writing', progress: runningTask.progress, status: runningTask.status })
}
```

2. 完成时刷新分支补（215-228 行附近，仿 directory 分支）：

```tsx
} else if (runningTask.task_type === 'continue_writing' && id) {
  queryClient.invalidateQueries({ queryKey: ['asset', id, 'directory'] })
  queryClient.invalidateQueries({ queryKey: ['chapters', id] })
  queryClient.invalidateQueries({ queryKey: ['project', id] })
  setDirectoryGenerating(false)
  setActiveTask(null)
}
```

- [ ] **Step 4: DirectoryTab 传参（863-877 行）**

```tsx
<DirectoryTab
  value={directoryText}
  onChange={(v) => { setDirectoryText(v); setDirty(true) }}
  loading={directoryLoading}
  saving={directorySaving}
  generating={directoryGenerating}
  activeTask={activeTask}
  projectId={project!.id}
  currentVersion={directory?.version ?? 0}
  onSave={handleSaveDirectory}
  onGenerate={handleGenerateDirectory}
  onExport={() => handleExportAsset('directory')}
  canContinue={project!.story_shape === 'open' && (!project!.total_chapters_target || project!.num_chapters < project!.total_chapters_target)}
  totalChaptersTarget={project!.total_chapters_target}
  numChapters={project!.num_chapters}
  onContinue={handleContinueWriting}
/>
```

- [ ] **Step 5: 验证**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit && npm run build`
Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/pages/ProjectDetail/DirectoryTab.tsx frontend/src/pages/ProjectDetail/index.tsx
git commit -m "feat: 目录 tab 续写入口（弹窗输入 k + 轮询 continue_writing 任务）"
```

---

### Task 12: 文档更新 + 全量回归

**Files:**
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/API_SPEC.md`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `backend/.env.example`（若存在则确认无需新增配置；本期无新环境变量，跳过）

- [ ] **Step 1: DATA_MODEL.md**

projects 表新增两列：

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `story_shape` | VARCHAR(20) | NOT NULL | `'final'` 短篇完结 / `'open'` 连载开篇；创建必选；允许修改 |
| `total_chapters_target` | INTEGER | NULL；open 必填 | 全书目标总章数 M；10~1000 且 > num_chapters；创建后不可修改；final 为 NULL |

并注明存量回填 `'open'/NULL`。

- [ ] **Step 2: API_SPEC.md**

- `POST /api/projects`：`story_shape` 必填（缺失 → 422）；`story_shape='open'` 时 `total_chapters_target` 必填且 10 ≤ M ≤ 1000、M > num_chapters（违反 → 422）。
- `PUT /api/projects/{id}`：拒绝修改 `total_chapters_target`（400："全书目标章数创建后不可修改"）；`story_shape` 可改：`open→final` 自动清空 M、`final→open` 必须补传 M（缺 → 400）。
- 新增 `POST /api/projects/{id}/generate/continue-writing`：body `{"chapters": k}`；非 open → 400；k < 1 → 422；M 存在且 N+k > M → 422；成功返回 TaskOut。
- 任务类型表补 `continue_writing`。

- [ ] **Step 3: CHANGELOG.md**

补一条变更记录（日期 2026-08-12）：故事形态前置收敛 + 续写闭环。

- [ ] **Step 4: ARCHITECTURE.md**

生成链路简述：architecture/directory 生成按 `story_shape` 注入形态指令（`_scope_statement` / `_architecture_shape_instruction` / `_directory_shape_instruction`）；`continue_writing` 任务三步串行（更新 num_chapters → `generate_directory_append` 追加目录（`_ensure_chapters(skip_existing=True)`）→ `_batch_generate_drafts` 增量正文）；批量正文增量语义（跳过已有 draft）。

- [ ] **Step 5: 全量回归（后端）**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest -x -q`
Expected: 全绿（含既有 16+ 条 asset_versions、project_router/service 等）。

- [ ] **Step 6: 全量回归（前端）**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit && npm run build`
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add docs/DATA_MODEL.md docs/API_SPEC.md docs/CHANGELOG.md docs/ARCHITECTURE.md
git commit -m "docs: 故事形态与续写闭环数据模型/API/架构/变更记录"
```

---

## Self-Review 核对

- **Spec coverage**：
  - 数据模型 + 回填 → Task 1 ✓
  - POST 422 校验（open 缺 M / 超范围 / ≤N）+ PUT 拒绝改 M + 形态转换 → Task 2 ✓
  - 架构生成 Step1 篇幅 + Step4 指令块 → Task 3 ✓
  - 目录生成第 N 章结局/阶段收束 → Task 4 ✓
  - 续写闭环：append_directory_prompt + _ensure_chapters 追加语义 + 增量正文 + num_chapters 更新 + k 越界拒绝 → Task 5/6/7 ✓
  - 前端创建表单（形态必选 + M 输入 + 锁定提示）→ Task 9 ✓
  - 前端设置页（形态可改、open→final 清 M、final→open 补 M、M 只读锁定）→ Task 10 ✓
  - 前端续写入口（open 且 N<M 显示、弹窗 k 校验、轮询）→ Task 11 ✓
  - 文档 → Task 12 ✓
  - 不实现项：正文第 M 章特殊分支（YAGNI）、architecture_consistency 启用（死代码）、M 中途修改（设计禁止）——均未在任务中出现 ✓
- **Placeholder scan**：无 TBD/TODO；每个任务含确切代码与测试。Task 6 循环体搬移以"原样搬入 + 标记边界"给出，属重构而非新代码。
- **Type consistency**：`_scope_statement`/`_architecture_shape_instruction`/`_directory_shape_instruction(project, end_num=None)`/`generate_directory_append(...)`/`_ensure_chapters(..., skip_existing=False)`/`_batch_generate_drafts(db, task_id, project, llm_config, structure, architecture_text, directory_text, world_state, template, chapter_list, total)`/`run_continue_writing_task(task_id)`/`run_continue_writing`/`generateContinueWriting` 在定义任务与消费任务间签名一致；前端 props 链（OverviewTab 4 props / DirectoryTab 4 props）Task 10/11 之间一致。
