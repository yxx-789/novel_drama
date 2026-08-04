# 小红书创作灵感功能实施计划（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V2 中新增「创作灵感」功能——独立的采集器每天把小红书热点写入数据库，App 只读数据库展示热点并支持一键导入项目、生成时参考。

**Architecture:** 采集与消费完全解耦：`scripts/xhs_hot_collector.py`（本地独立运行，连小红书 MCP）→ 写入 `hot_topics` 表；V2 后端只读该表（3 个 API），前端「灵感」Tab 消费。客户端不暴露数据来源是小红书。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（async）+ Alembic + React/TypeScript + 采集器用同步 `requests` + `psycopg2-binary`。

## Global Constraints

- 前端/API **不得出现「小红书」字样**；`source` 字段只存 DB，不返回给前端
- 运行时 V2 App **零 MCP/小红书依赖**（采集是独立脚本）
- 采集器用同步库（requests + psycopg2），不依赖 FastAPI 异步环境
- 数据库字段**不用 `desc`**（PostgreSQL 保留字），用 `summary`
- 所有 API 走现有 JWT 鉴权（`get_current_user`）+ 项目 owner 隔离（`get_project_by_id`）
- 预设分类唯一真源：`backend/app/core/preset_categories.py`（采集器和后端服务都从它读）
- 本功能只在 V2 本地开发，VPS 稳定版不动

---

### Task 1: HotTopic 模型 + Alembic 迁移

**Files:**
- Create: `backend/app/models/inspiration.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/xxxx_add_hot_topics_table.py`（autogenerate）

**Interfaces:**
- Consumes: `app.models.base.Base, UUIDMixin, TimestampMixin`
- Produces: `HotTopic`（字段：id/category/note_id/title/summary/likes/collects/shares/url/author/source/fetched_at），`note_id` 唯一约束

- [ ] **Step 1: 写模型文件** `backend/app/models/inspiration.py`

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class HotTopic(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "hot_topics"
    __table_args__ = (
        UniqueConstraint("note_id", name="uq_hot_topics_note_id"),
    )

    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    note_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    collects: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    url: Mapped[str | None] = mapped_column(String(512))
    author: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(32), default="xiaohongshu")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
```

- [ ] **Step 2: 注册模型** `backend/app/models/__init__.py` 追加 `from app.models.inspiration import HotTopic`

- [ ] **Step 3: 生成迁移**（后端容器内，代码挂载自动生效）

```bash
docker compose exec -T backend alembic revision --autogenerate -m "add hot topics table"
docker compose exec -T backend alembic upgrade head
```

预期：`Running upgrade ... -> ... add hot topics table`

- [ ] **Step 4: 验证表存在**

```bash
docker compose exec -T db psql -U postgres -d ai_novel_studio -c "\d hot_topics"
```

预期：显示 hot_topics 表结构，含 `note_id` 唯一约束 `uq_hot_topics_note_id`。

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/inspiration.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add HotTopic model and migration"
```

---

### Task 2: 预设分类配置（唯一真源）

**Files:**
- Create: `backend/app/core/preset_categories.py`

**Interfaces:**
- Produces: `PRESET_CATEGORIES: list[dict]`，每项 `{"name": str, "keywords": list[str]}`；`get_preset_category_names() -> list[str]`；`get_keywords(name) -> list[str]`

- [ ] **Step 1: 写配置模块**

```python
"""预设分类 → 搜索关键词映射（唯一真源，采集器与后端共用）。"""

PRESET_CATEGORIES = [
    {"name": "热门话题", "keywords": ["热门", "热搜", "爆款"]},
    {"name": "小说推荐", "keywords": ["小说推荐", "热门小说", "书荒"]},
    {"name": "短剧", "keywords": ["短剧", "短剧剧本", "微短剧"]},
    {"name": "影视改编", "keywords": ["小说改编", "影视化", "IP 改编"]},
    {"name": "写作技巧", "keywords": ["写作技巧", "写小说", "新手写作"]},
    {"name": "玄幻", "keywords": ["玄幻小说", "玄幻"]},
    {"name": "仙侠修仙", "keywords": ["修仙小说", "仙侠", "长生"]},
    {"name": "都市", "keywords": ["都市小说", "都市脑洞"]},
    {"name": "重生", "keywords": ["重生文", "重生"]},
    {"name": "穿越", "keywords": ["穿越文", "架空历史"]},
    {"name": "历史权谋", "keywords": ["历史小说", "大明", "三国"]},
    {"name": "悬疑灵异", "keywords": ["悬疑小说", "灵异", "惊悚"]},
    {"name": "科幻末世", "keywords": ["科幻小说", "末世", "无限流"]},
    {"name": "系统流", "keywords": ["系统流", "面板流", "签到"]},
    {"name": "高武", "keywords": ["高武", "无敌流"]},
    {"name": "游戏电竞", "keywords": ["电竞小说", "游戏文"]},
    {"name": "军事战争", "keywords": ["军事小说", "军旅"]},
    {"name": "武侠", "keywords": ["武侠小说", "江湖"]},
    {"name": "同人二创", "keywords": ["同人文", "火影同人", "斗罗同人"]},
    {"name": "甜宠", "keywords": ["甜宠文", "甜文"]},
    {"name": "现代言情", "keywords": ["现代言情", "都市言情"]},
    {"name": "古代言情", "keywords": ["古代言情", "古言"]},
    {"name": "豪门总裁", "keywords": ["总裁文", "豪门", "霸总"]},
    {"name": "宫斗宅斗", "keywords": ["宫斗", "宅斗"]},
    {"name": "快穿", "keywords": ["快穿文"]},
    {"name": "娱乐圈", "keywords": ["娱乐圈小说", "顶流"]},
    {"name": "校园青春", "keywords": ["校园小说", "青春"]},
    {"name": "先婚后爱", "keywords": ["先婚后爱"]},
    {"name": "追妻火葬场", "keywords": ["追妻火葬场"]},
    {"name": "真假千金", "keywords": ["真假千金", "千金"]},
    {"name": "萌宝", "keywords": ["萌宝", "团宠", "奶爸"]},
    {"name": "年代文", "keywords": ["年代文", "七零", "八零"]},
]


def get_preset_category_names() -> list[str]:
    return [c["name"] for c in PRESET_CATEGORIES]


def get_keywords(name: str) -> list[str]:
    for c in PRESET_CATEGORIES:
        if c["name"] == name:
            return c["keywords"]
    return []
```

- [ ] **Step 2: 写单元测试** `backend/app/tests/test_preset_categories.py`

```python
from app.core.preset_categories import get_preset_category_names, get_keywords


def test_has_32_categories():
    assert len(get_preset_category_names()) == 32


def test_each_category_has_keywords():
    for name in get_preset_category_names():
        assert get_keywords(name), f"{name} 缺关键词"


def test_unknown_category_returns_empty():
    assert get_keywords("不存在") == []
```

- [ ] **Step 3: 跑测试**

```bash
docker compose exec -T backend python -m pytest app/tests/test_preset_categories.py -q
```

预期：3 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/preset_categories.py backend/app/tests/test_preset_categories.py
git commit -m "feat: add preset inspiration categories"
```

---

### Task 3: inspiration_service（读 DB + 导入）

**Files:**
- Create: `backend/app/services/inspiration_service.py`

**Interfaces:**
- Consumes: `HotTopic`（Task 1）、`PRESET_CATEGORIES`（Task 2）
- Produces:
  - `async def get_hot_notes(db, category: str | None, keyword: str | None, limit: int = 20) -> list[dict]`
  - `async def import_inspiration(db, project, note: dict) -> Project`
  - `async def build_inspiration_guidance(db, project_id: str) -> str`

- [ ] **Step 1: 写 service**

```python
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inspiration import HotTopic
from app.models.project import Project, ProjectAsset


async def get_hot_notes(
    db: AsyncSession,
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """读最近一批 hot_topics，按点赞降序。keyword 对 title/summary 做模糊过滤（只搜已采集数据）。"""
    latest = await db.execute(
        select(HotTopic.fetched_at).order_by(HotTopic.fetched_at.desc()).limit(1)
    )
    latest_ts = latest.scalar_one_or_none()

    stmt = select(HotTopic).order_by(HotTopic.likes.desc()).limit(limit)
    if latest_ts is not None:
        stmt = stmt.where(HotTopic.fetched_at == latest_ts)
    if category:
        stmt = stmt.where(HotTopic.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where((HotTopic.title.ilike(like)) | (HotTopic.summary.ilike(like)))

    result = await db.execute(stmt)
    notes = result.scalars().all()
    return [
        {
            "note_id": n.note_id,
            "title": n.title,
            "summary": n.summary,
            "likes": n.likes,
            "collects": n.collects,
            "url": n.url,
            "author": n.author,
            "fetched_at": n.fetched_at,
        }
        for n in notes
    ]


async def import_inspiration(db: AsyncSession, project: Project, note: dict) -> Project:
    """设项目主题 + 存 inspiration 资产。幂等：重复导入同一灵感覆盖 asset。"""
    if note.get("title"):
        project.topic = note["title"]
        await db.flush()

    content = {
        "note_id": note.get("note_id"),
        "title": note.get("title"),
        "summary": note.get("summary"),
        "likes": note.get("likes"),
        "url": note.get("url"),
        "author": note.get("author"),
        "tags": note.get("tags", []),
    }
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == str(project.id),
            ProjectAsset.asset_type == "inspiration",
        )
    )
    asset = result.scalar_one_or_none()
    if asset:
        asset.content_json = content
        asset.version += 1
    else:
        asset = ProjectAsset(
            project_id=str(project.id),
            asset_type="inspiration",
            content_json=content,
        )
        db.add(asset)
    await db.commit()
    await db.refresh(project)
    return project


async def build_inspiration_guidance(db: AsyncSession, project_id: str) -> str:
    """读取项目已导入的灵感资产，格式化为生成 prompt 的创作引导。"""
    result = await db.execute(
        select(ProjectAsset).where(
            ProjectAsset.project_id == project_id,
            ProjectAsset.asset_type == "inspiration",
        )
    )
    asset = result.scalar_one_or_none()
    if not asset or not asset.content_json:
        return ""
    c = asset.content_json
    lines = [f"- 标题：{c.get('title', '')}"]
    if c.get("summary"):
        lines.append(f"- 摘要：{c['summary']}")
    if c.get("tags"):
        lines.append(f"- 标签：{'、'.join(c['tags'])}")
    if c.get("likes"):
        lines.append(f"- 热度：{c['likes']} 赞")
    return "\n".join(lines)
```

- [ ] **Step 2: 单元测试纯逻辑**（`build_inspiration_guidance` 的格式化，DB 函数用 mock）

`backend/app/tests/test_inspiration_service.py`

```python
import asyncio
from types import SimpleNamespace

import pytest

from app.services.inspiration_service import build_inspiration_guidance


class FakeResult:
    def scalar_one_or_none(self):
        return SimpleNamespace(
            content_json={
                "title": "重生之我在都市当神豪",
                "summary": "主角重生九十年代逆袭",
                "tags": ["重生", "都市", "神豪"],
                "likes": 5200,
            }
        )


class FakeExecute:
    def __call__(self, stmt):
        return FakeResult()


class FakeDB:
    def execute(self, stmt):
        return FakeExecute()(stmt)


def test_build_guidance_formats_asset():
    db = FakeDB()
    result = asyncio.run(build_inspiration_guidance(db, "p1"))
    assert "重生之我在都市当神豪" in result
    assert "5200" in result
    assert "重生、都市、神豪" in result
```

- [ ] **Step 3: 跑测试**

```bash
docker compose exec -T backend python -m pytest app/tests/test_inspiration_service.py -q
```

预期：1 passed

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/inspiration_service.py backend/app/tests/test_inspiration_service.py
git commit -m "feat: add inspiration service (read hot topics, import, guidance)"
```

---

### Task 4: inspiration router + 挂载

**Files:**
- Create: `backend/app/routers/inspiration.py`
- Modify: `backend/app/main.py`（挂载）

**Interfaces:**
- Consumes: `get_hot_notes` / `import_inspiration`（Task 3）、`get_preset_category_names`（Task 2）
- Produces: `GET /api/inspiration/categories`、`GET /api/inspiration/hot`、`POST /api/projects/{project_id}/inspiration`

- [ ] **Step 1: 写 router**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.preset_categories import get_preset_category_names
from app.infra.database import get_db
from app.models.user import User
from app.routers.dependency import get_current_user
from app.services.inspiration_service import get_hot_notes, import_inspiration
from app.services.project_service import get_project_by_id

router = APIRouter()


@router.get("/inspiration/categories")
async def list_categories():
    return get_preset_category_names()


@router.get("/inspiration/hot")
async def list_hot_notes(
    category: str | None = None,
    keyword: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_hot_notes(db, category=category, keyword=keyword, limit=limit)


@router.post("/projects/{project_id}/inspiration")
async def import_note(
    project_id: uuid.UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await get_project_by_id(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在或无权限访问")
    project = await import_inspiration(db, project, payload)
    return {"success": True, "topic": project.topic}
```

- [ ] **Step 2: main.py 挂载**（`from app.routers import ... inspiration`，`app.include_router(inspiration.router, prefix="/api", tags=["inspiration"])`）

- [ ] **Step 3: 手动验证**（V2 后端容器已跑；V2 本地库是全新的，先注册用户）

先插入一条测试数据：

```bash
docker compose exec -T db psql -U postgres -d ai_novel_studio -c "INSERT INTO hot_topics (id, category, note_id, title, summary, likes, collects, shares, url, author, source, fetched_at) VALUES (gen_random_uuid(), '甜宠', 'note-test-1', '测试甜宠热点', '测试摘要', 999, 100, 10, 'http://x', '作者A', 'xiaohongshu', now());"
```

注册 + 登录拿 token + 调接口：

```bash
curl -s -X POST http://localhost:8000/api/auth/register -H "Content-Type: application/json" -d '{"username":"insp_test","email":"insp_test@example.com","password":"Test123456"}' >/dev/null
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"insp_test","password":"Test123456"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/inspiration/hot?category=甜宠"
```

预期：返回包含 `测试甜宠热点` 的列表，且**没有 source 字段**。

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/inspiration.py backend/app/main.py
git commit -m "feat: add inspiration API endpoints"
```

---

### Task 5: 生成时参考（注入 user_guidance）

**Files:**
- Modify: `backend/app/services/task_service.py`（`run_architecture_task` / `run_directory_task`）

**Interfaces:**
- Consumes: `build_inspiration_guidance`（Task 3）

- [ ] **Step 1: 在 task_service 注入灵感引导**

在 `run_architecture_task` 里 `user_guidance` 读取后、调用 `generate_architecture` 前，追加：

```python
from app.services.inspiration_service import build_inspiration_guidance

# 在 user_guidance 赋值后：
try:
    guidance = await build_inspiration_guidance(db, str(task.project_id))
    if guidance:
        user_guidance = f"{user_guidance}\n\n【创作灵感参考】\n{guidance}".strip()
except Exception as e:
    logger.warning(f"Inspiration guidance injection failed: {e}")
```

同样的逻辑加到 `run_directory_task` 的 `user_guidance` 读取后。

- [ ] **Step 2: 验证**——给一个项目导入灵感资产后触发架构生成，worker 日志应出现 `【创作灵感参考】`

```bash
# 用 API 导入灵感（会设主题 + 写 inspiration asset）
PROJECT_ID=<你的项目id>
TOKEN=<上一步登录的 token>
curl -s -X POST "http://localhost:8000/api/projects/$PROJECT_ID/inspiration" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"note_id":"note-1","title":"测试灵感","summary":"测试摘要","likes":100,"url":"http://x","author":"作者"}'

# 触发架构生成
curl -s -X POST "http://localhost:8000/api/projects/$PROJECT_ID/generate/architecture" \
  -H "Authorization: Bearer $TOKEN"

# 看 worker 日志确认注入
docker compose logs -f worker | grep "创作灵感参考"
```

预期：worker 日志/生成任务带 `【创作灵感参考】` 且任务 success。

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/task_service.py
git commit -m "feat: inject inspiration guidance into generation"
```

---

### Task 6: 采集器（独立脚本）

**Files:**
- Create: `scripts/xhs_hot_collector.py`
- Create: `scripts/mcp_client.py`（同步 MCP 客户端，从 `xhs-get/xhs-query-go/mcp_client.py` 移植）
- Create: `scripts/launchd.example.plist`（定时示例）
- Create: `scripts/requirements.txt`

**Interfaces:**
- Consumes: `PRESET_CATEGORIES`（Task 2，经 `sys.path` 引入 `backend`）
- Produces: 写 `hot_topics` 表（按 `note_id` UPSERT）

- [ ] **Step 1: 同步 MCP 客户端** `scripts/mcp_client.py`（移植自 `xhs-get/xhs-query-go/mcp_client.py`，核心不变：`initialize` → `Mcp-Session-Id` → `tools/call`）

```python
"""Defensive MCP Streamable-HTTP client for xiaohongshu-mcp（同步版）。"""
import json
import threading
import time
from typing import Any

import requests


class McpClient:
    def __init__(self, url: str, timeout: int = 180, max_retries: int = 2, request_interval: float = 0.8):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = max(0.0, request_interval)
        self._session = requests.Session()
        self._session_id: str | None = None
        self._req_id = 0
        self._last_request_at = 0.0

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _throttle(self) -> None:
        remaining = self.request_interval - (time.monotonic() - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)

    def _post(self, payload: dict, expect_body: bool = True) -> dict:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        for attempt in range(self.max_retries + 1):
            try:
                self._throttle()
                resp = self._session.post(self.url, headers=headers, json=payload, timeout=self.timeout)
                self._last_request_at = time.monotonic()
                resp.raise_for_status()
                if not self._session_id:
                    self._session_id = resp.headers.get("Mcp-Session-Id")
                if not expect_body:
                    return {}
                ct = resp.headers.get("content-type", "")
                if "text/event-stream" in ct:
                    for line in resp.text.splitlines():
                        if line.startswith("data:"):
                            raw = line[5:].strip()
                            if raw and raw != "[DONE]":
                                return json.loads(raw)
                    return {}
                return resp.json() if resp.content else {}
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise RuntimeError(f"MCP request failed: {exc}") from exc
                time.sleep(1.5 * (2**attempt))

    def connect(self) -> None:
        body = self._post({
            "jsonrpc": "2.0", "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "novel-drama-collector", "version": "1.0.0"}},
            "id": self._next_id(),
        })
        if body.get("error"):
            raise RuntimeError(f"MCP initialize error: {body['error']}")
        if not self._session_id:
            raise RuntimeError("MCP initialize did not return Mcp-Session-Id")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, expect_body=False)

    def call_tool(self, name: str, arguments: dict | None = None) -> Any:
        body = self._post({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
            "id": self._next_id(),
        })
        if body.get("error"):
            raise RuntimeError(f"Tool {name} RPC error: {body['error']}")
        result = body.get("result") or {}
        text = "\n".join(
            item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"
        )
        if result.get("isError"):
            raise RuntimeError(f"Tool {name} error: {text}")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
```

- [ ] **Step 2: 写采集器** `scripts/xhs_hot_collector.py`

```python
"""小红书热点采集器：每天把热点写入 hot_topics 表。独立运行，不参与 Web 服务。"""
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

import psycopg2
from psycopg2.extras import execute_batch

# 让 preset_categories 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.preset_categories import PRESET_CATEGORIES  # noqa: E402
from mcp_client import McpClient  # noqa: E402

XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060/mcp")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_novel_studio")
TOP_N_PER_CATEGORY = int(os.getenv("TOP_N_PER_CATEGORY", "20"))


def _find_list(value: Any, key: str) -> list[dict]:
    if isinstance(value, dict):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        for child in value.values():
            found = _find_list(child, key)
            if found:
                return found
    return []


def normalize_feeds(feeds: list[dict], category: str) -> list[dict]:
    """把 MCP search 返回的 feeds 规范成入库行。"""
    rows = []
    for f in feeds:
        note = f if isinstance(f, dict) else {}
        title = note.get("title") or note.get("displayTitle") or ""
        if not title:
            continue
        row = {
            "category": category,
            "note_id": str(note.get("noteId") or note.get("feedId") or ""),
            "title": str(title)[:255],
            "summary": (note.get("desc") or note.get("summary") or "")[:2000],
            "likes": int((note.get("interactInfo") or {}).get("likedCount") or 0),
            "collects": int((note.get("interactInfo") or {}).get("collectedCount") or 0),
            "shares": int((note.get("interactInfo") or {}).get("shareCount") or 0),
            "url": note.get("url") or "",
            "author": (note.get("user") or {}).get("nickname") or "",
            "source": "xiaohongshu",
        }
        rows.append(row)
    return rows


def upsert_hot_topics(rows: list[dict]) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            sql = """
                INSERT INTO hot_topics
                    (id, category, note_id, title, summary, likes, collects, shares, url, author, source, fetched_at)
                VALUES (gen_random_uuid(), %(category)s, %(note_id)s, %(title)s, %(summary)s,
                        %(likes)s, %(collects)s, %(shares)s, %(url)s, %(author)s, %(source)s, now())
                ON CONFLICT (note_id) DO UPDATE SET
                    likes = EXCLUDED.likes,
                    collects = EXCLUDED.collects,
                    shares = EXCLUDED.shares,
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    fetched_at = EXCLUDED.fetched_at
            """
            execute_batch(cur, sql, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def collect_once() -> dict:
    client = McpClient(XHS_MCP_URL)
    client.connect()
    total = 0
    errors = []
    try:
        for cat in PRESET_CATEGORIES:
            cat_rows: list[dict] = []
            for kw in cat["keywords"]:
                try:
                    result = client.call_tool("search_feeds", {"keyword": kw})
                    feeds = _find_list(result, "feeds")
                    cat_rows.extend(normalize_feeds(feeds, cat["name"]))
                except Exception as e:
                    errors.append(f"{cat['name']}/{kw}: {e}")
            # 按点赞排序取 Top N
            cat_rows.sort(key=lambda r: r["likes"], reverse=True)
            cat_rows = cat_rows[:TOP_N_PER_CATEGORY]
            if cat_rows:
                total += upsert_hot_topics(cat_rows)
    finally:
        client.close()
    return {"total_upserted": total, "errors": errors}


if __name__ == "__main__":
    report = collect_once()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        print("部分分类失败（可能未登录或限流）:", report["errors"])
```

- [ ] **Step 3: 依赖** `scripts/requirements.txt`

```
requests
psycopg2-binary
```

- [ ] **Step 4: 定时配置示例** `scripts/launchd.example.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.noveldrama.xhs-collector</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/yxx/Desktop/novel_drama_v2/scripts/xhs_hot_collector.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>30</integer></dict>
    <key>StandardOutPath</key><string>/tmp/xhs-collector.log</string>
    <key>StandardErrorPath</key><string>/tmp/xhs-collector.err.log</string>
</dict>
</plist>
```

- [ ] **Step 5: 单元测试**（`normalize_feeds` 纯函数）`scripts/test_collector.py`

```python
from xhs_hot_collector import normalize_feeds

FEEDS = [
    {"title": "甜宠文推荐", "noteId": "a1", "interactInfo": {"likedCount": 100}},
    {"title": "", "noteId": "a2", "interactInfo": {"likedCount": 1}},
]

def test_normalize_filters_empty_title():
    rows = normalize_feeds(FEEDS, "甜宠")
    assert len(rows) == 1
    assert rows[0]["title"] == "甜宠文推荐"
    assert rows[0]["likes"] == 100
    assert rows[0]["category"] == "甜宠"
    assert rows[0]["source"] == "xiaohongshu"
```

跑：`cd scripts && python3 -m pytest test_collector.py -q`（需 `pip install requests psycopg2-binary`）

- [ ] **Step 6: Commit**

```bash
git add scripts/
git commit -m "feat: add xhs hot topics collector script"
```

---

### Task 7: 前端「灵感」Tab

**Files:**
- Create: `frontend/src/api/inspiration.ts`
- Create: `frontend/src/pages/ProjectDetail/InspirationTab.tsx`
- Modify: `frontend/src/pages/ProjectDetail/index.tsx`（TabKey + tabs + 渲染）

**Interfaces:**
- Consumes: `GET /api/inspiration/categories`、`GET /api/inspiration/hot`、`POST /api/projects/{project_id}/inspiration`（Task 4）

- [ ] **Step 1: API 模块** `frontend/src/api/inspiration.ts`

```ts
import apiClient from './client'

export interface HotNote {
  note_id: string
  title: string
  summary: string | null
  likes: number
  collects: number
  url: string | null
  author: string | null
  fetched_at: string
}

export const getInspirationCategories = async (): Promise<string[]> => {
  const response = await apiClient.get<string[]>('/api/inspiration/categories')
  return response.data
}

export const getHotNotes = async (category?: string, keyword?: string): Promise<HotNote[]> => {
  const response = await apiClient.get<HotNote[]>('/api/inspiration/hot', {
    params: { category: category || undefined, keyword: keyword || undefined },
  })
  return response.data
}

export const importInspiration = async (
  projectId: string,
  note: HotNote
): Promise<{ success: boolean; topic: string }> => {
  const response = await apiClient.post(`/api/projects/${projectId}/inspiration`, note)
  return response.data
}
```

- [ ] **Step 2: InspirationTab 组件** `frontend/src/pages/ProjectDetail/InspirationTab.tsx`

```tsx
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getInspirationCategories, getHotNotes, importInspiration, HotNote } from '../../api/inspiration'
import { useToastStore } from '../../store/toast'

interface Props {
  projectId: string
}

export default function InspirationTab({ projectId }: Props) {
  const { addToast } = useToastStore()
  const [category, setCategory] = useState('')
  const [keyword, setKeyword] = useState('')

  const { data: categories = [] } = useQuery({
    queryKey: ['inspirationCategories'],
    queryFn: getInspirationCategories,
  })

  const { data: notes = [], refetch } = useQuery({
    queryKey: ['inspirationHot', category, keyword],
    queryFn: () => getHotNotes(category, keyword),
  })

  const importMut = useMutation({
    mutationFn: (note: HotNote) => importInspiration(projectId, note),
    onSuccess: (data) => addToast(`已导入灵感：${data.topic}`, 'success'),
    onError: (err: any) => addToast(err?.response?.data?.detail || '导入失败', 'error'),
  })

  const handleImport = (note: HotNote) => {
    if (window.confirm(`将「${note.title}」设为项目主题并作为创作参考？`)) {
      importMut.mutate(note)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => { setCategory(''); setKeyword(''); refetch() }}
          className="text-xs px-3 py-1.5 rounded-full bg-white border border-slate-200 text-slate-600 hover:bg-slate-50">
          全部
        </button>
        {categories.map((c) => (
          <button key={c} onClick={() => setCategory(c)}
            className={`text-xs px-3 py-1.5 rounded-full border ${
              category === c ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}>
            {c}
          </button>
        ))}
        <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索标题/摘要…"
          className="ml-auto w-48 bg-slate-50 border border-slate-200 rounded-lg py-1.5 px-3 text-sm" />
        <button onClick={() => refetch()}
          className="text-xs px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-600 hover:bg-slate-50">
          刷新
        </button>
      </div>

      {notes.length === 0 ? (
        <p className="text-sm text-slate-400 italic">暂无热点数据，请先运行采集器更新。</p>
      ) : (
        <div className="space-y-2">
          {notes.map((note) => (
            <div key={note.note_id} className="flex items-start justify-between bg-white rounded-lg border border-slate-200/70 px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{note.title}</p>
                {note.summary && <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{note.summary}</p>}
                <p className="text-xs text-slate-400 mt-1">👍 {note.likes} · {note.author || '未知作者'}</p>
              </div>
              <button onClick={() => handleImport(note)}
                className="shrink-0 ml-3 text-xs px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700">
                导入项目
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: 接入 Tab** `frontend/src/pages/ProjectDetail/index.tsx`
  - `TabKey` 联合类型追加 `| 'inspiration'`
  - `tabs` 数组追加 `{ key: 'inspiration', label: '创作灵感' }`
  - 条件渲染追加 `<InspirationTab projectId={pid} />`

- [ ] **Step 4: 构建验证**

```bash
cd frontend && npm run build
```

预期：tsc + vite build 通过，零错误。

- [ ] **Step 5: 手动验证**——V2 前端打开项目 → 「创作灵感」Tab → 分类 chips 显示、列表渲染、点「导入项目」→ toast 提示、项目主题变为该标题。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/inspiration.ts frontend/src/pages/ProjectDetail/InspirationTab.tsx frontend/src/pages/ProjectDetail/index.tsx
git commit -m "feat: add inspiration tab to project detail"
```

---

### Task 8: 文档同步

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/API_SPEC.md`

- [ ] **Step 1: CHANGELOG** 在 `[未发布]` 新增「创作灵感功能」小节，记录：hot_topics 表、3 个 API、采集器脚本、灵感 Tab、生成注入。

- [ ] **Step 2: API_SPEC** 登记 `GET /api/inspiration/categories`、`GET /api/inspiration/hot`、`POST /api/projects/{id}/inspiration` 三个接口。

- [ ] **Step 3: Commit**

```bash
git add docs/CHANGELOG.md docs/API_SPEC.md
git commit -m "docs: document inspiration feature"
```

---

## 验收清单

- [ ] `hot_topics` 表存在，`note_id` 唯一约束生效
- [ ] 采集器连上 MCP 后能把热点写入 DB（每天一次）
- [ ] `GET /api/inspiration/hot` 返回按点赞排序的热点，**不含 source 字段**
- [ ] 前端「创作灵感」Tab 可浏览/搜索/刷新，一键导入设主题
- [ ] 导入灵感后生成架构，prompt 含「创作灵感参考」
- [ ] 全程前端/API 无「小红书」字样
- [ ] 现有功能（登录/项目/生成/短剧）回归正常
