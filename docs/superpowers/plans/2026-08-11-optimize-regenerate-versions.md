# 架构/目录：基于当前内容优化重新生成 + 版本历史回滚 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 架构/目录两个 asset 支持传入作者优化提示词（guidance）后基于当前全文重新生成，并把每次生成/手动保存/回滚写入独立 `asset_versions` 表，支持列表查看与一键回滚。

**Architecture:** 新增 `asset_versions` 表存全量历史（`ProjectAsset` 表结构不变，`version` 继续作当前版本指针）。提示词链路走现有管道：路由 body → `task.params` → worker → `generation_service` prompt。前端架构/目录两个 tab 对称接入可展开优化面板（`GuidancePanel`）+ 版本历史列表（`VersionHistory`）。

**Tech Stack:** FastAPI + SQLAlchemy(async) + Alembic + Celery；React 18 + TanStack Query + Vite；pytest。

## Global Constraints

- 数据模型迁移链尾：`down_revision = '3bae85f20ef6'`（当前 alembic 最新迁移）
- 版本历史仅覆盖 `asset_type ∈ ("architecture", "directory")`；其他 asset 类型（world_state 等）行为与现状完全一致（不写历史、不递增多余内容）
- guidance 最大 2000 字，超长返回 400
- 无 guidance 的生成请求体不带 body 字段（与旧行为兼容）
- 回滚**永不删除**历史行；回滚写回内容、version 续 +1，并新增 trigger=rollback 行
- 手工保存（`PUT /assets/{type}`）对 architecture/directory 写 trigger=manual 历史行
- 迁移需回填存量：现有 architecture/directory 内容作为 version=1（trigger=manual）
- 后端测试运行：`cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/<file> -v`
- 前端类型检查：`cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit`

---

### Task 1: `asset_versions` 表（模型 + 迁移 + 存量回填）

**Files:**
- Create: `backend/alembic/versions/a1b2c3d4e5f6_add_asset_versions.py`
- Modify: `backend/app/models/project.py`（末尾追加 `AssetVersion` 类）

**Interfaces:**
- Consumes: `Base`、`UUIDMixin`、`TimestampMixin`（`app.models.base`）
- Produces: `AssetVersion` 模型（字段：`project_id`、`asset_type`、`version`、`content_text`、`trigger_type`、`guidance`、`created_by`）；迁移 `a1b2c3d4e5f6`（down_revision=`3bae85f20ef6`）

- [ ] **Step 1: 追加模型**

在 `backend/app/models/project.py` 末尾（`Task` 类后、`DramaEpisode` 前任意位置均可，追加在 `ProjectAsset` 后即可）添加：

```python
class AssetVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "asset_versions"

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="generate")
    guidance: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
```

- [ ] **Step 2: 写迁移文件**

创建 `backend/alembic/versions/a1b2c3d4e5f6_add_asset_versions.py`：

```python
"""add asset_versions table

Revision ID: a1b2c3d4e5f6
Revises: 3bae85f20ef6
Create Date: 2026-08-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3bae85f20ef6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('asset_versions',
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('asset_type', sa.String(length=50), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content_text', sa.Text(), nullable=False),
    sa.Column('trigger_type', sa.String(length=20), nullable=False),
    sa.Column('guidance', sa.Text(), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'asset_type', 'version', name='uq_asset_versions_project_type_version')
    )
    op.create_index(op.f('ix_asset_versions_project_type_version'), 'asset_versions', ['project_id', 'asset_type', 'version'], unique=True)

    # 存量回填：现有 architecture/directory 内容作为 v1（trigger=manual）
    bind = op.get_bind()
    bind.execute(sa.text(
        """
        INSERT INTO asset_versions
            (id, project_id, asset_type, version, content_text, trigger_type, created_at, updated_at)
        SELECT gen_random_uuid(), project_id, asset_type, 1, content_text, 'manual', now(), now()
        FROM project_assets
        WHERE asset_type IN ('architecture', 'directory')
          AND content_text IS NOT NULL AND content_text != ''
        """
    ))


def downgrade() -> None:
    op.drop_index(op.f('ix_asset_versions_project_type_version'), table_name='asset_versions')
    op.drop_table('asset_versions')
```

- [ ] **Step 3: 验证模型可导入 + 迁移可编译**

Run:
```bash
cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -c "from app.models.project import AssetVersion; print(AssetVersion.__tablename__)" && .venv/bin/python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; s = ScriptDirectory.from_config(Config('alembic.ini')); print([h for h in s.walk_revisions()][0].revision)"
```
Expected: 输出 `asset_versions`；head revision 为 `a1b2c3d4e5f6`

- [ ] **Step 4: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add backend/alembic/versions/a1b2c3d4e5f6_add_asset_versions.py backend/app/models/project.py && git commit -m "feat: asset_versions 表（模型 + 迁移 + 存量回填 v1）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: prompt 注入「参考当前版本」（`prompts.py` + `generation_service.py`）

**Files:**
- Modify: `backend/app/generator/prompts.py`（5 个 prompt 模板加占位符）
- Modify: `backend/app/services/generation_service.py`（helper + 两个生成函数签名 + format 注入）
- Test: `backend/app/tests/test_asset_versions.py`（新建，本 task 只加注入测试类）

**Interfaces:**
- Consumes: 现有 `core_seed_prompt`、`character_dynamics_prompt`、`world_building_prompt`、`plot_architecture_prompt`、`chapter_blueprint_prompt`
- Produces:
  - `_current_content_section(current_content: str, asset_name: str) -> str`（generation_service 模块级函数；空内容返回 `""`）
  - `generate_architecture(project, user_guidance="", current_content="", llm_config=None)`（新增 `current_content`，默认空串，不破坏现有调用）
  - `generate_directory(project, architecture_text="", user_guidance="", current_content="", llm_config=None)`
  - prompt 模板新增占位符 `{current_content_section}`

- [ ] **Step 1: 写失败测试**

创建 `backend/app/tests/test_asset_versions.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: `FAILED` — `TypeError: generate_architecture() got an unexpected keyword argument 'current_content'`

- [ ] **Step 3: 实现**

`backend/app/generator/prompts.py` —— 在 **5 个**模板中加入 `{current_content_section}` 占位符：

- `core_seed_prompt`（约第 9-25 行）：在 `{structure_seed_guidance}` 之后、`仅返回故事核心文本` 之前插入一行：

```
{current_content_section}

仅返回故事核心文本，不要解释任何内容。
```

- `character_dynamics_prompt`（第 28-54 行）：在 `- 核心种子：{core_seed}` 行之后插入：

```
{current_content_section}
```

- `world_building_prompt`（第 57-86 行）：在 `- 核心冲突："{core_seed}"` 行之后插入：

```
{current_content_section}
```

- `plot_architecture_prompt`（第 183-203 行）：在 `- 世界观：{world_building}` 行之后插入：

```
{current_content_section}
```

- `chapter_blueprint_prompt`（第 303-340 行）：在 `- 小说架构：`/`{novel_architecture}` 块之后插入：

```
{current_content_section}
```

`backend/app/services/generation_service.py`：

- 在 `_invoke_with_retry` 函数后新增模块级 helper：

```python
def _current_content_section(current_content: str, asset_name: str) -> str:
    """构造「参考当前版本」prompt 段；无当前内容时返回空串（不占 prompt）。"""
    text = (current_content or "").strip()
    if not text:
        return ""
    return (
        f"【参考当前版本】\n"
        f"以下是当前已有的{asset_name}全文，请基于它优化：保留其合理设定，"
        f"针对作者要求调整，不要从零重写、不要丢失已有核心设定。\n\n"
        f"{text}"
    )
```

- `generate_architecture` 签名改为：

```python
async def generate_architecture(
    project: Project,
    user_guidance: str = "",
    current_content: str = "",
    llm_config: dict | None = None,
) -> tuple[str, str]:
```

- 在函数体内（`guidance = build_structure_guidance(...)` 之后）加：

```python
    current_section = _current_content_section(current_content, "架构")
```

- Step 1（`core_seed_prompt.format(...)`）的实参中追加 `current_content_section=current_section`；
- Step 2/3/4（`character_dynamics_prompt`/`world_building_prompt`/`plot_architecture_prompt` 的 `.format(...)`）各自实参追加 `current_content_section=current_section`；
- Step 5（`create_character_state_prompt`）**不注入**（角色状态基于角色动力学生成，与当前架构无关）。

- `generate_directory` 签名改为：

```python
async def generate_directory(
    project: Project,
    architecture_text: str = "",
    user_guidance: str = "",
    current_content: str = "",
    llm_config: dict | None = None,
) -> tuple[str, list[dict]]:
```

- 在函数体内加：

```python
    current_section = _current_content_section(current_content, "目录")
```

- `chapter_blueprint_prompt.format(...)` 实参追加 `current_content_section=current_section`。

- [ ] **Step 4: 运行确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: 4 passed

- [ ] **Step 5: 回归既有 prompt 测试**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_p3a_wiring.py app/tests/test_structure_guidance.py app/tests/test_p3b_wiring.py -v`
Expected: 全部 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/tests/test_asset_versions.py && git commit -m "feat: 架构/目录生成注入「参考当前版本」prompt 段

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 版本写入与回滚 service（`task_service.py`）

**Files:**
- Modify: `backend/app/services/task_service.py`
- Test: `backend/app/tests/test_asset_versions.py`（追加）

**Interfaces:**
- Consumes: `AssetVersion`（Task 1）、`_current_content_section`（Task 2，本 task 不用，仅后续 worker 用）
- Produces:
  - `VERSIONED_ASSET_TYPES = ("architecture", "directory")`（模块级常量）
  - `record_asset_version(db, project_id, asset_type, content_text, version, trigger_type="generate", guidance=None, created_by=None) -> None`（仅对 versioned 类型写行，独立 commit）
  - `_save_asset(db, project_id, asset_type, content_text, trigger_type="generate", guidance=None, created_by=None)`（新增 3 个可选参数；对 versioned 类型在写 ProjectAsset 后同步写历史行；其他类型行为不变）
  - `rollback_asset(db, project_id, asset_type, version, user_id=None) -> bool`（目标版本不存在返回 False；存在则写回 ProjectAsset、version 续 +1、写 trigger=rollback 行、返回 True）

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py）**

```python
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

    async def execute(self, stmt):
        return _FakeResult(self.results.pop(0) if self.results else None)

    def add(self, obj):
        pass

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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -k "Version or Rollback" -v`
Expected: FAILED — `ImportError`/`AttributeError`（函数不存在 / 未写历史行）

- [ ] **Step 3: 实现**

`backend/app/services/task_service.py`：

- import 处追加：

```python
from app.models.project import AssetVersion
```

- 在 `_save_asset` 定义前新增：

```python
VERSIONED_ASSET_TYPES = ("architecture", "directory")


async def record_asset_version(
    db: AsyncSession,
    project_id: str,
    asset_type: str,
    content_text: str,
    version: int,
    trigger_type: str = "generate",
    guidance: str | None = None,
    created_by: str | None = None,
) -> None:
    """把一次写入记入 asset_versions 历史表（仅 architecture/directory）。"""
    if asset_type not in VERSIONED_ASSET_TYPES:
        return
    db.add(AssetVersion(
        project_id=project_id,
        asset_type=asset_type,
        content_text=content_text,
        version=version,
        trigger_type=trigger_type,
        guidance=guidance,
        created_by=created_by,
    ))
    await db.commit()
```

- 替换 `_save_asset` 为：

```python
async def _save_asset(
    db: AsyncSession,
    project_id: str,
    asset_type: str,
    content_text: str,
    trigger_type: str = "generate",
    guidance: str | None = None,
    created_by: str | None = None,
) -> None:
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_text = content_text
        asset.version += 1
        asset.updated_by = created_by
    else:
        asset = ProjectAsset(
            project_id=project_id,
            asset_type=asset_type,
            content_text=content_text,
            version=1,
            updated_by=created_by,
        )
        db.add(asset)
    await db.commit()
    await db.refresh(asset)
    if asset_type in VERSIONED_ASSET_TYPES:
        await record_asset_version(
            db,
            project_id,
            asset_type,
            content_text,
            version=asset.version,
            trigger_type=trigger_type,
            guidance=guidance,
            created_by=created_by,
        )
```

- 新增回滚函数（放在 `_save_asset` 之后）：

```python
async def rollback_asset(
    db: AsyncSession,
    project_id: str,
    asset_type: str,
    version: int,
    user_id: str | None = None,
) -> bool:
    """把指定历史版本写回当前 asset；成功返回 True，目标版本不存在返回 False。"""
    result = await db.execute(
        select(AssetVersion).where(
            AssetVersion.project_id == project_id,
            AssetVersion.asset_type == asset_type,
            AssetVersion.version == version,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        return False

    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_text = target.content_text
        asset.version += 1
        asset.updated_by = user_id
    else:
        asset = ProjectAsset(
            project_id=project_id,
            asset_type=asset_type,
            content_text=target.content_text,
            version=1,
            updated_by=user_id,
        )
        db.add(asset)
    await db.commit()
    await db.refresh(asset)
    await record_asset_version(
        db,
        project_id,
        asset_type,
        target.content_text,
        version=asset.version,
        trigger_type="rollback",
        guidance=f"回滚至 v{version}",
        created_by=user_id,
    )
    return True
```

- [ ] **Step 4: 运行确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: 7 passed（4 注入 + 3 写入/回滚）

- [ ] **Step 5: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add backend/app/services/task_service.py backend/app/tests/test_asset_versions.py && git commit -m "feat: asset 版本历史写入与回滚 service

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: worker 接线（读取 current_content 并传参）

**Files:**
- Modify: `backend/app/services/task_service.py`
- Test: `backend/app/tests/test_asset_versions.py`（追加）

**Interfaces:**
- Consumes: `generate_architecture` / `generate_directory` 新签名（Task 2）、`_save_asset` 新签名（Task 3）
- Produces: `run_architecture_task` / `run_directory_task` 行为变化：读取 `params["current_content"]` 传入生成函数；`_save_asset` 以原始（未拼接灵感）guidance 写历史行

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py）**

```python
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
            id="t1", project_id="p1",
            params={"project_id": "p1", "user_guidance": "侧重人物", "current_content": "现有架构"},
        )
        mock_proj.return_value = project
        mock_llm.return_value = {"api_key": "k"}
        mock_insp.return_value = None
        mock_gen.return_value = ("新架构", "新角色")
        db = FakeDB(results=[task])
        with patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_architecture_task("t1"))
        _, kwargs = mock_gen.call_args
        assert kwargs["current_content"] == "现有架构"
        # _save_asset 以原始 guidance（未拼接灵感）写历史
        assert mock_save.call_args.kwargs["guidance"] == "侧重人物"

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
            id="t1", project_id="p1",
            params={"project_id": "p1", "user_guidance": "节奏加快", "current_content": "现有目录"},
        )
        mock_proj.return_value = project
        mock_llm.return_value = {"api_key": "k"}
        mock_insp.return_value = None
        mock_gen.return_value = ("新目录", [{"chapter_number": 1}])
        db = FakeDB(results=[task])
        with patch("app.services.task_service.AsyncSessionLocal", return_value=db):
            _run(run_directory_task("t1"))
        _, kwargs = mock_gen.call_args
        assert kwargs["current_content"] == "现有目录"
        assert mock_save.call_args.kwargs["guidance"] == "节奏加快"
```

> 注：`run_architecture_task`/`run_directory_task` 内有多次 `update_task_status(db, ...)`，FakeDB 未实现 `get_task_by_id` 所依赖的查询顺序（第 1 次 execute 返回 task 行）。为让测试可跑通，上面 `AsyncSessionLocal` 替换的 db 需要能处理该流程：测试中先给 FakeDB 传 `results=[task]`（`get_task_by_id` 第一次查询）。若后续实现变更导致查询顺序变化，按实际顺序补 `results`。

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -k WorkerWiring -v`
Expected: FAILED — `generate_architecture() got an unexpected keyword argument 'current_content'`（worker 未传参）

- [ ] **Step 3: 实现**

`backend/app/services/task_service.py`：

`run_architecture_task` 内，把第 141-143 行改为：

```python
            user_guidance = ""
            current_content = ""
            if task.params and isinstance(task.params, dict):
                user_guidance = task.params.get("user_guidance", "")
                current_content = task.params.get("current_content", "")
            raw_guidance = user_guidance  # 未拼接灵感的原始提示词，用于版本历史记录
```

`generate_architecture(...)` 调用改为：

```python
            architecture_text, character_state_text = await generate_architecture(
                project,
                user_guidance=user_guidance,
                current_content=current_content,
                llm_config=llm_config,
            )
```

两个 `_save_asset` 调用改为：

```python
            await _save_asset(db, str(task.project_id), "architecture", architecture_text,
                              trigger_type="generate", guidance=raw_guidance)
            await _save_asset(db, str(task.project_id), "characters", character_state_text)
```

`run_directory_task` 内，把第 240-242 行改为：

```python
            user_guidance = ""
            current_content = ""
            if task.params and isinstance(task.params, dict):
                user_guidance = task.params.get("user_guidance", "")
                current_content = task.params.get("current_content", "")
            raw_guidance = user_guidance
```

`generate_directory(...)` 调用改为：

```python
            directory_text, parsed_chapters = await generate_directory(
                project,
                architecture_text=architecture_text,
                user_guidance=user_guidance,
                current_content=current_content,
                llm_config=llm_config,
            )
```

`_save_asset(db, ..., "directory", directory_text)` 改为：

```python
            await _save_asset(db, str(task.project_id), "directory", directory_text,
                              trigger_type="generate", guidance=raw_guidance)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add backend/app/services/task_service.py backend/app/tests/test_asset_versions.py && git commit -m "feat: 架构/目录 worker 读取 current_content 并记录原始 guidance

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 生成路由接收 guidance + 快照当前内容（`generate.py`）

**Files:**
- Modify: `backend/app/routers/generate.py`
- Test: `backend/app/tests/test_asset_versions.py`（追加）

**Interfaces:**
- Consumes: `create_task`、`get_project_by_id`（现有）
- Produces:
  - `POST /api/projects/{project_id}/generate/architecture` 与 `.../directory` 接受可选 body `{"guidance": "..."}`；guidance > 2000 字 → 400
  - task.params 新增 `user_guidance` + `current_content`（提交时从 asset 表取当前全文快照）

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py）**

```python
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
                id="task-1", project_id=str(project_id), task_type=task_type,
                status="pending", params=params, progress=0,
                result=None, error_msg=None,
                created_at="2026-08-11T00:00:00+00:00",
                updated_at="2026-08-11T00:00:00+00:00",
            )
            return task

        # 项目存在 + 当前架构快照
        project = SimpleNamespace(id="p1")
        db = FakeDB(results=[project, SimpleNamespace(content_text="现有架构全文")])
        client = self._make_client(db)
        with patch("app.routers.generate.get_project_by_id", return_value=project), \
             patch("app.routers.generate.create_task", side_effect=_fake_create_task), \
             patch("app.routers.generate.run_architecture.delay") as mock_delay:
            res = client.post("/api/projects/p1/generate/architecture", json={"guidance": "侧重群像"})
        self._clear_overrides(client)
        assert res.status_code == 200, res.text
        assert captured["params"]["user_guidance"] == "侧重群像"
        assert captured["params"]["current_content"] == "现有架构全文"
        mock_delay.assert_called_once_with("task-1")

    def test_guidance_too_long_returns_400(self):
        from app.routers.generate import GUIDANCE_MAX_LEN

        project = SimpleNamespace(id="p1")
        db = FakeDB(results=[project])
        client = self._make_client(db)
        with patch("app.routers.generate.get_project_by_id", return_value=project):
            res = client.post(
                "/api/projects/p1/generate/architecture",
                json={"guidance": "长" * (GUIDANCE_MAX_LEN + 1)},
            )
        self._clear_overrides(client)
        assert res.status_code == 400, res.text
        assert "优化提示词" in res.json()["detail"]
```

> 注：`get_project_by_id(db, project_id, current_user.id)` 带三个参数，因此必须 patch `app.routers.generate.get_project_by_id`（不能用 FakeDB 的 execute 返回）。

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -k GenerateRouterGuidance -v`
Expected: FAILED — 400（当前路由不收 body，超长不校验；params 无 guidance）

- [ ] **Step 3: 实现**

`backend/app/routers/generate.py`：

- import 追加：

```python
from sqlalchemy import select
from app.models.project import ProjectAsset
```

- 模块常量（router 定义前）：

```python
GUIDANCE_MAX_LEN = 2000
```

- 本地 helper（`router = APIRouter()` 之后）：

```python
async def _get_current_asset_text(db: AsyncSession, project_id: str, asset_type: str) -> str | None:
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    return asset.content_text if asset else None


def _validate_guidance(payload: dict) -> str:
    guidance = (payload.get("guidance") or "").strip()
    if len(guidance) > GUIDANCE_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"优化提示词不能超过 {GUIDANCE_MAX_LEN} 字")
    return guidance
```

- `trigger_architecture_generation` 改为：

```python
@router.post("/projects/{project_id}/generate/architecture", response_model=TaskOut)
async def trigger_architecture_generation(
    project_id: uuid.UUID,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    guidance = _validate_guidance(payload)
    current_content = await _get_current_asset_text(db, str(project_id), "architecture")
    task = await create_task(
        db, project_id, "architecture",
        params={
            "project_id": str(project_id),
            "user_guidance": guidance,
            "current_content": current_content,
        },
    )
    run_architecture.delay(str(task.id))
    return task
```

- `trigger_directory_generation` 改为：

```python
@router.post("/projects/{project_id}/generate/directory", response_model=TaskOut)
async def trigger_directory_generation(
    project_id: uuid.UUID,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    guidance = _validate_guidance(payload)
    current_content = await _get_current_asset_text(db, str(project_id), "directory")
    task = await create_task(
        db, project_id, "directory",
        params={
            "project_id": str(project_id),
            "user_guidance": guidance,
            "current_content": current_content,
        },
    )
    run_directory.delay(str(task.id))
    return task
```

- [ ] **Step 4: 运行确认通过**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: 11 passed

- [ ] **Step 5: 回归其他生成路由**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_project_router.py -v`
Expected: passed

- [ ] **Step 6: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add backend/app/routers/generate.py backend/app/tests/test_asset_versions.py && git commit -m "feat: 生成路由接收优化提示词并快照当前内容

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 版本 API + 手动保存写历史（`assets.py`）

**Files:**
- Modify: `backend/app/routers/assets.py`
- Test: `backend/app/tests/test_asset_versions.py`（追加）

**Interfaces:**
- Consumes: `record_asset_version`、`rollback_asset`（Task 3）
- Produces:
  - `GET /api/projects/{project_id}/assets/{asset_type}/versions` → `[{id, version, trigger_type, guidance, created_at}]`（按 version 倒序）
  - `POST /api/projects/{project_id}/assets/{asset_type}/rollback` body `{"version": N}` → 目标不存在 404；成功返回当前 asset（同 GET 结构）
  - `PUT /api/projects/{project_id}/assets/{asset_type}` 对 architecture/directory 追加写 trigger=manual 历史行

- [ ] **Step 1: 写失败测试（追加到 test_asset_versions.py）**

```python
class TestVersionsRouter:
    """版本列表 + 回滚端点。"""

    def test_list_versions_returns_desc(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.database import get_db
        from app.routers.dependency import get_current_user
        from app.models.user import User

        rows = [
            SimpleNamespace(id="v1", version=2, trigger_type="generate", guidance="优化", created_at="2026-08-11T00:02:00+00:00"),
            SimpleNamespace(id="v2", version=1, trigger_type="manual", guidance=None, created_at="2026-08-11T00:01:00+00:00"),
        ]

        class _RowsResult:
            def scalars(self):
                return SimpleNamespace(all=lambda: rows)

        async def _fake_get_db():
            yield FakeDB(results=[])

        async def _fake_get_current_user():
            u = User()
            u.id = str(uuid.uuid4())
            return u

        app.dependency_overrides[get_db] = _fake_get_db
        app.dependency_overrides[get_current_user] = _fake_get_current_user
        client = TestClient(app, raise_server_exceptions=False)

        project = SimpleNamespace(id="p1")
        with patch("app.routers.assets.get_project_by_id", return_value=project), \
             patch("app.routers.assets.db_versions_execute") as m:
            m.return_value = _RowsResult()
            res = client.get("/api/projects/p1/assets/architecture/versions")
        app.dependency_overrides.clear()
        assert res.status_code == 200, res.text
        body = res.json()
        assert [b["version"] for b in body] == [2, 1]
        assert body[0]["trigger_type"] == "generate"

    def test_rollback_returns_404_when_missing(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.database import get_db
        from app.routers.dependency import get_current_user
        from app.models.user import User

        async def _fake_get_db():
            yield FakeDB(results=[])

        async def _fake_get_current_user():
            u = User()
            u.id = str(uuid.uuid4())
            return u

        app.dependency_overrides[get_db] = _fake_get_db
        app.dependency_overrides[get_current_user] = _fake_get_current_user
        client = TestClient(app, raise_server_exceptions=False)

        project = SimpleNamespace(id="p1")
        with patch("app.routers.assets.get_project_by_id", return_value=project), \
             patch("app.routers.assets.rollback_asset", return_value=False):
            res = client.post("/api/projects/p1/assets/architecture/rollback", json={"version": 99})
        app.dependency_overrides.clear()
        assert res.status_code == 404, res.text

    def test_rollback_invalid_version_returns_400(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.database import get_db
        from app.routers.dependency import get_current_user
        from app.models.user import User

        async def _fake_get_db():
            yield FakeDB(results=[])

        async def _fake_get_current_user():
            u = User()
            u.id = str(uuid.uuid4())
            return u

        app.dependency_overrides[get_db] = _fake_get_db
        app.dependency_overrides[get_current_user] = _fake_get_current_user
        client = TestClient(app, raise_server_exceptions=False)

        project = SimpleNamespace(id="p1")
        with patch("app.routers.assets.get_project_by_id", return_value=project):
            res = client.post("/api/projects/p1/assets/architecture/rollback", json={"version": "abc"})
        app.dependency_overrides.clear()
        assert res.status_code == 400, res.text
```

> 注：`GET versions` 路由测试里用 `patch("app.routers.assets.db_versions_execute")` 是占位符，**实现时改为真实 SQL** 后，此 patch 目标名失效，需把该测试改成不 patch（FakeDB results 顺序喂给 execute）。实现完成后按实际代码调整该测试（见 Step 4 说明）。

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -k VersionsRouter -v`
Expected: FAILED — 404（路由不存在）

- [ ] **Step 3: 实现**

`backend/app/routers/assets.py`：

- import 追加：

```python
from app.models.project import AssetVersion
from app.services.task_service import record_asset_version, rollback_asset
```

- 在 `get_asset` 之后、`upsert_asset` 之前新增：

```python
@router.get("/projects/{project_id}/assets/{asset_type}/versions")
async def list_asset_versions(
    project_id: uuid.UUID,
    asset_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的资产类型: {asset_type}")
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    result = await db.execute(
        select(AssetVersion).where(
            AssetVersion.project_id == str(project_id),
            AssetVersion.asset_type == asset_type,
        ).order_by(AssetVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version": v.version,
            "trigger_type": v.trigger_type,
            "guidance": v.guidance,
            "created_at": v.created_at,
        }
        for v in versions
    ]


@router.post("/projects/{project_id}/assets/{asset_type}/rollback")
async def rollback_asset_endpoint(
    project_id: uuid.UUID,
    asset_type: str,
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if asset_type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的资产类型: {asset_type}")
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    version = payload.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise HTTPException(status_code=400, detail="version 参数无效")
    ok = await rollback_asset(db, str(project_id), asset_type, version, str(current_user.id))
    if not ok:
        raise HTTPException(status_code=404, detail="目标版本不存在")

    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project_id),
            ProjectAsset.asset_type == asset_type,
        )
    )
    asset = result.scalar_one_or_none()
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "asset_type": asset.asset_type,
        "content_text": asset.content_text,
        "content_json": asset.content_json,
        "version": asset.version,
        "updated_at": asset.updated_at,
    }
```

- `upsert_asset` 改造（`await db.commit()` 之后、`return` 之前追加）：

```python
    if asset_type in ("architecture", "directory"):
        await record_asset_version(
            db,
            str(project_id),
            asset_type,
            content_text or "",
            version=asset.version,
            trigger_type="manual",
            guidance=None,
            created_by=str(current_user.id),
        )
```

- [ ] **Step 4: 修正 GET versions 测试并运行**

把 `test_list_versions_returns_desc` 改为不 patch（真实 SQL 走 FakeDB 队列）——将 `results=[]` 改为喂入版本行，删除 `db_versions_execute` patch：

```python
    def test_list_versions_returns_desc(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.infra.database import get_db
        from app.routers.dependency import get_current_user
        from app.models.user import User

        rows = [
            SimpleNamespace(id="v1", version=2, trigger_type="generate", guidance="优化", created_at="2026-08-11T00:02:00+00:00"),
            SimpleNamespace(id="v2", version=1, trigger_type="manual", guidance=None, created_at="2026-08-11T00:01:00+00:00"),
        ]

        class _RowsResult:
            def scalars(self):
                return SimpleNamespace(all=lambda: rows)

        class _ExecuteDB(FakeDB):
            async def execute(self, stmt):
                return _RowsResult()

        async def _fake_get_db():
            yield _ExecuteDB()

        async def _fake_get_current_user():
            u = User()
            u.id = str(uuid.uuid4())
            return u

        app.dependency_overrides[get_db] = _fake_get_db
        app.dependency_overrides[get_current_user] = _fake_get_current_user
        client = TestClient(app, raise_server_exceptions=False)

        project = SimpleNamespace(id="p1")
        with patch("app.routers.assets.get_project_by_id", return_value=project):
            res = client.get("/api/projects/p1/assets/architecture/versions")
        app.dependency_overrides.clear()
        assert res.status_code == 200, res.text
        body = res.json()
        assert [b["version"] for b in body] == [2, 1]
        assert body[0]["trigger_type"] == "generate"
```

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests/test_asset_versions.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add backend/app/routers/assets.py backend/app/tests/test_asset_versions.py && git commit -m "feat: 版本列表/回滚 API + 手动保存写历史

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 前端 API 层（`asset.ts` + `generate.ts`）

**Files:**
- Modify: `frontend/src/api/asset.ts`
- Modify: `frontend/src/api/generate.ts`

**Interfaces:**
- Consumes: `apiClient`（`./client`）
- Produces:
  - `AssetVersion` 接口、`getAssetVersions(projectId, assetType): Promise<AssetVersion[]>`
  - `rollbackAsset(projectId, assetType, version): Promise<Asset>`
  - `generateArchitecture(projectId, guidance?)` / `generateDirectory(projectId, guidance?)`（有 guidance 才带 body）

- [ ] **Step 1: 实现 asset.ts 追加**

```ts
export interface AssetVersion {
  id: string
  version: number
  trigger_type: 'generate' | 'manual' | 'rollback'
  guidance: string | null
  created_at: string
}

export const getAssetVersions = async (projectId: string, assetType: string): Promise<AssetVersion[]> => {
  const response = await apiClient.get<AssetVersion[]>(`/api/projects/${projectId}/assets/${assetType}/versions`)
  return response.data
}

export const rollbackAsset = async (projectId: string, assetType: string, version: number): Promise<Asset> => {
  const response = await apiClient.post<Asset>(`/api/projects/${projectId}/assets/${assetType}/rollback`, { version })
  return response.data
}
```

- [ ] **Step 2: 实现 generate.ts 修改**

```ts
export const generateArchitecture = async (projectId: string, guidance?: string): Promise<Task> => {
  const response = await apiClient.post<Task>(
    `/api/projects/${projectId}/generate/architecture`,
    guidance ? { guidance } : undefined
  )
  return response.data
}

export const generateDirectory = async (projectId: string, guidance?: string): Promise<Task> => {
  const response = await apiClient.post<Task>(
    `/api/projects/${projectId}/generate/directory`,
    guidance ? { guidance } : undefined
  )
  return response.data
}
```

- [ ] **Step 3: 类型检查**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 4: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add frontend/src/api/asset.ts frontend/src/api/generate.ts && git commit -m "feat: 前端 API 层（版本列表/回滚 + 生成带 guidance）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: `GuidancePanel` + `VersionHistory` 组件

**Files:**
- Create: `frontend/src/components/GuidancePanel.tsx`
- Create: `frontend/src/components/VersionHistory.tsx`

**Interfaces:**
- Consumes: `useQuery`/`useQueryClient`（`@tanstack/react-query`）、`getAssetVersions`/`rollbackAsset`（Task 7）、`useToastStore`
- Produces:
  - `GuidancePanel({ assetName, generating, onGenerateWithGuidance })`：可展开面板（textarea + 带提示词生成按钮），默认收起
  - `VersionHistory({ projectId, assetType, assetName, currentVersion })`：版本列表 + 回滚，内部 invalidate `['asset', projectId, assetType]` 与 `['asset-versions', projectId, assetType]`

- [ ] **Step 1: 创建 GuidancePanel.tsx**

```tsx
import { useState } from 'react'

interface GuidancePanelProps {
  assetName: string
  generating: boolean
  onGenerateWithGuidance: (guidance: string) => void
}

export default function GuidancePanel({ assetName, generating, onGenerateWithGuidance }: GuidancePanelProps) {
  const [open, setOpen] = useState(false)
  const [guidance, setGuidance] = useState('')

  return (
    <div className="shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors ${
          open
            ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
            : 'border-gray-300 text-gray-600 hover:bg-gray-50'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        优化提示词
        <svg className={`w-3 h-3 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="mt-2 p-3 bg-indigo-50/40 border border-indigo-100 rounded-xl">
          <textarea
            value={guidance}
            onChange={(e) => setGuidance(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 text-sm leading-relaxed rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-100 resize-y"
            placeholder={`告诉模型想怎么优化当前${assetName}：侧重什么、调整什么、保留什么…`}
          />
          <div className="flex items-center justify-between mt-2">
            <span className="text-[10px] text-slate-400">将基于当前{assetName}全文 + 你的提示词重新生成</span>
            <button
              onClick={() => {
                onGenerateWithGuidance(guidance.trim())
              }}
              disabled={generating}
              className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0 text-xs py-1.5 px-4"
            >
              {generating ? '生成中...' : `带提示词生成${assetName}`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: 创建 VersionHistory.tsx**

```tsx
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getAssetVersions, rollbackAsset } from '../api/asset'
import { useToastStore } from '../store/toast'

interface VersionHistoryProps {
  projectId: string
  assetType: string
  assetName: string
  currentVersion: number
}

const TRIGGER_LABEL: Record<string, string> = {
  generate: 'AI 生成',
  manual: '手动保存',
  rollback: '回滚',
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  return d.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function VersionHistory({
  projectId,
  assetType,
  assetName,
  currentVersion,
}: VersionHistoryProps) {
  const [open, setOpen] = useState(false)
  const [rolling, setRolling] = useState<number | null>(null)
  const queryClient = useQueryClient()
  const toast = useToastStore((s) => s.addToast)

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ['asset-versions', projectId, assetType],
    queryFn: () => getAssetVersions(projectId, assetType),
    enabled: open,
  })

  const handleRollback = async (version: number) => {
    if (!window.confirm(`确定回滚到 v${version} 吗？当前${assetName}将被替换（历史版本仍保留）。`)) return
    setRolling(version)
    try {
      await rollbackAsset(projectId, assetType, version)
      await queryClient.invalidateQueries({ queryKey: ['asset', projectId, assetType] })
      await queryClient.invalidateQueries({ queryKey: ['asset-versions', projectId, assetType] })
      toast(`已回滚到 v${version}`, 'success')
    } catch (err: any) {
      toast(err.response?.data?.detail || '回滚失败', 'warning')
    } finally {
      setRolling(null)
    }
  }

  return (
    <div className="shrink-0">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-1 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors ${
          open
            ? 'border-indigo-300 bg-indigo-50 text-indigo-700'
            : 'border-gray-300 text-gray-600 hover:bg-gray-50'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        版本历史
        <span className="text-[10px] text-slate-400">v{currentVersion}</span>
      </button>

      {open && (
        <div className="mt-2 bg-white border border-slate-200 rounded-xl max-h-64 overflow-y-auto">
          {isLoading ? (
            <p className="text-xs text-slate-400 text-center py-4">加载中...</p>
          ) : versions.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-4">暂无历史版本</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {versions.map((v) => (
                <li key={v.id} className="px-3 py-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium text-slate-700">v{v.version}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                        {TRIGGER_LABEL[v.trigger_type] || v.trigger_type}
                      </span>
                      {v.version === currentVersion && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-600">当前</span>
                      )}
                    </div>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {formatTime(v.created_at)}
                      {v.guidance ? ` · ${v.guidance.slice(0, 30)}${v.guidance.length > 30 ? '…' : ''}` : ''}
                    </p>
                  </div>
                  {v.version !== currentVersion && (
                    <button
                      onClick={() => handleRollback(v.version)}
                      disabled={rolling !== null}
                      className="shrink-0 text-[10px] px-2 py-1 rounded-md border border-slate-200 text-slate-500 hover:bg-indigo-50 hover:border-indigo-200 hover:text-indigo-600 transition-colors disabled:opacity-50"
                    >
                      {rolling === v.version ? '回滚中...' : '回滚到此版本'}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 类型检查**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 4: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add frontend/src/components/GuidancePanel.tsx frontend/src/components/VersionHistory.tsx && git commit -m "feat: 优化提示词面板 + 版本历史组件

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: 架构/目录 tab 集成（`ArchitectureTab` / `DirectoryTab` / `index.tsx`）

**Files:**
- Modify: `frontend/src/pages/ProjectDetail/ArchitectureTab.tsx`
- Modify: `frontend/src/pages/ProjectDetail/DirectoryTab.tsx`
- Modify: `frontend/src/pages/ProjectDetail/index.tsx`

**Interfaces:**
- Consumes: `GuidancePanel`、`VersionHistory`（Task 8）、`generateArchitecture(projectId, guidance?)`/`generateDirectory(projectId, guidance?)`（Task 7）
- Produces:
  - `ArchitectureTab`/`DirectoryTab` 新增 props：`projectId: string`、`currentVersion: number`；`onGenerate` 签名改为 `(guidance?: string) => void`
  - `index.tsx`：`handleGenerateArchitecture(guidance?)`/`handleGenerateDirectory(guidance?)` 透传 guidance；tab 生成按钮文案随有无内容切换；渲染 GuidancePanel + VersionHistory

- [ ] **Step 1: 修改 ArchitectureTab.tsx**

- 导入：

```tsx
import GuidancePanel from '../../components/GuidancePanel'
import VersionHistory from '../../components/VersionHistory'
```

- Props 接口改为：

```tsx
interface ArchitectureTabProps {
  value: string
  onChange: (v: string) => void
  characterText: string
  loading: boolean
  saving: boolean
  generating: boolean
  activeTask: { id: string; type: string; progress: number; status: string } | null
  projectId: string
  currentVersion: number
  onSave: () => void
  onGenerate: (guidance?: string) => void
  onExport: () => void
}
```

- 解构处加 `projectId, currentVersion`。
- 生成按钮（第 151-157 行）替换为：

```tsx
          <button
            onClick={() => onGenerate()}
            disabled={generating}
            className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {generating ? '生成中...' : value.trim() ? '基于当前架构优化生成' : 'AI 生成架构'}
          </button>
          <GuidancePanel
            assetName="架构"
            generating={generating}
            onGenerateWithGuidance={(g) => onGenerate(g)}
          />
          <VersionHistory
            projectId={projectId}
            assetType="architecture"
            assetName="架构"
            currentVersion={currentVersion}
          />
```

- [ ] **Step 2: 修改 DirectoryTab.tsx**

- 导入同上（GuidancePanel / VersionHistory）。
- Props 接口与解构同步增加 `projectId: string`、`currentVersion: number`，`onGenerate: (guidance?: string) => void`。
- 生成按钮替换为：

```tsx
          <button
            onClick={() => onGenerate()}
            disabled={generating}
            className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {generating ? '生成中...' : value.trim() ? '基于当前目录优化生成' : 'AI 生成目录'}
          </button>
          <GuidancePanel
            assetName="目录"
            generating={generating}
            onGenerateWithGuidance={(g) => onGenerate(g)}
          />
          <VersionHistory
            projectId={projectId}
            assetType="directory"
            assetName="目录"
            currentVersion={currentVersion}
          />
```

- [ ] **Step 3: 修改 index.tsx**

- `handleGenerateArchitecture` 签名与调用改为：

```tsx
  const handleGenerateArchitecture = async (guidance?: string) => {
    if (!id) return
    setArchitectureGenerating(true)
    try {
      const task = await generateArchitecture(id, guidance)
      ...
```

- `handleGenerateDirectory` 签名与调用改为：

```tsx
  const handleGenerateDirectory = async (guidance?: string) => {
    if (!id) return
    setDirectoryGenerating(true)
    try {
      const task = await generateDirectory(id, guidance)
      ...
```

- `ArchitectureTab` 渲染处（第 847-858 行）增加 props：

```tsx
          <ArchitectureTab
            value={architectureText}
            onChange={(v) => { setArchitectureText(v); setDirty(true) }}
            characterText={characters?.content_text || ''}
            loading={architectureLoading}
            saving={architectureSaving}
            generating={architectureGenerating}
            activeTask={activeTask}
            projectId={project!.id}
            currentVersion={architecture?.version ?? 0}
            onSave={handleSaveArchitecture}
            onGenerate={handleGenerateArchitecture}
            onExport={() => handleExportAsset('architecture')}
          />
```

- `DirectoryTab` 渲染处（第 862-873 行）同步：

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
          />
```

- [ ] **Step 4: 类型检查**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npx tsc --noEmit`
Expected: 无报错

- [ ] **Step 5: 构建验证**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npm run build`
Expected: 构建成功（tsc + vite build 通过）

- [ ] **Step 6: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add frontend/src/pages/ProjectDetail/ArchitectureTab.tsx frontend/src/pages/ProjectDetail/DirectoryTab.tsx frontend/src/pages/ProjectDetail/index.tsx && git commit -m "feat: 架构/目录 tab 接入优化面板与版本历史

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: 文档更新 + 全量回归

**Files:**
- Modify: `docs/API_SPEC.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 更新 docs/API_SPEC.md**

在生成接口段（`POST /api/projects/{id}/generate/architecture`、`.../directory`）补充：

```
请求体（可选）：
{
  "guidance": "作者优化提示词，最长 2000 字；超长返回 400"
}
行为：任务执行时基于当前已有内容全文 + guidance 优化生成；task.params 含
user_guidance 与 current_content（提交时快照）。
```

新增版本 API 两节：

```
### 资产版本列表
GET /api/projects/{id}/assets/{asset_type}/versions
返回：[{ id, version, trigger_type, guidance, created_at }]（version 倒序）
trigger_type: generate | manual | rollback

### 资产版本回滚
POST /api/projects/{id}/assets/{asset_type}/rollback
请求体：{ "version": N }
行为：把 vN 内容写回当前 asset（version 续 +1），新增 trigger=rollback 历史行；
目标版本不存在返回 404；version 参数非法返回 400。
```

- [ ] **Step 2: 更新 docs/DATA_MODEL.md**

新增表：

```
### asset_versions（版本历史）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects | |
| asset_type | str(50) | architecture / directory（仅这两类写历史） |
| version | int | 该 asset 下序号，从 1 递增 |
| content_text | text | 该版本完整内容 |
| trigger_type | str(20) | generate / manual / rollback |
| guidance | text 可空 | 生成时的优化提示词；rollback 记「回滚至 vN」 |
| created_by | UUID 可空 | |
| created_at / updated_at | timestamptz | |
唯一约束：(project_id, asset_type, version)
```

- [ ] **Step 3: 更新 docs/CHANGELOG.md**

追加变更记录条目：架构/目录支持基于当前内容优化重新生成（生成接口接收 guidance、prompt 注入当前全文）、新增 asset_versions 版本历史表与版本列表/回滚 API、手动保存亦记录历史版本。

- [ ] **Step 4: 全量后端回归**

Run: `cd /Users/yxx/novel_drama_v2/backend && .venv/bin/python -m pytest app/tests -v -q`
Expected: 全部 passed

- [ ] **Step 5: 全量前端构建回归**

Run: `cd /Users/yxx/novel_drama_v2/frontend && npm run build`
Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
cd /Users/yxx/novel_drama_v2 && git add docs/API_SPEC.md docs/DATA_MODEL.md docs/CHANGELOG.md && git commit -m "docs: 版本历史 API / 数据模型 / 变更记录

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 执行顺序与依赖

1. Task 1（表）→ 2（prompt 注入）→ 3（写入/回滚 service）→ 4（worker 接线）→ 5（生成路由）→ 6（版本 API）→ 7（前端 API）→ 8（组件）→ 9（tab 集成）→ 10（文档 + 回归）
2. Task 3 依赖 Task 1 的 `AssetVersion`；Task 4 依赖 Task 2/3；Task 5/6 依赖 Task 3；Task 9 依赖 Task 7/8。
3. 每个 Task 独立提交，独立可验证。
