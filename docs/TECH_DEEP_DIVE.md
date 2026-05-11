# AI 小说 & 短剧创作工作台 —— 技术全景解析

## 目录

1. [系统概览](#1-系统概览)
2. [技术栈选型与理由](#2-技术栈选型与理由)
3. [后端架构详解](#3-后端架构详解)
4. [前端架构详解](#4-前端架构详解)
5. [核心功能技术实现](#5-核心功能技术实现)
6. [数据模型设计](#6-数据模型设计)
7. [AI/LLM 集成架构](#7-aillm-集成架构)
8. [异步任务引擎](#8-异步任务引擎)
9. [世界状态系统（核心壁垒）](#9-世界状态系统核心壁垒)
10. [安全架构](#10-安全架构)
11. [部署与运维架构](#11-部署与运维架构)
12. [性能与扩展性设计](#12-性能与扩展性设计)
13. [测试策略](#13-测试策略)
14. [技术债务与演进路线](#14-技术债务与演进路线)

---

## 1. 系统概览

### 1.1 系统边界

```
用户浏览器
    │
    ▼
┌─────────────────────────────────────────┐
│  React SPA (Vercel CDN)                 │
│  - 静态资源 (JS/CSS)                     │
│  - 全局状态管理                          │
└─────────────────────────────────────────┘
    │ HTTPS
    ▼
┌─────────────────────────────────────────┐
│  Render / VPS (Docker)                  │
│  ┌─────────────────────────────────┐    │
│  │  Supervisor 进程管理             │    │
│  │  ├── FastAPI (HTTP API)         │    │
│  │  └── Celery Worker (任务执行)    │    │
│  └─────────────────────────────────┘    │
│         │                               │
│  ┌──────┴──────┐  ┌─────────────────┐   │
│  │ PostgreSQL  │  │ Redis           │   │
│  │ (数据持久化) │  │ (队列/缓存)      │   │
│  └─────────────┘  └─────────────────┘   │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│  外部 LLM API                           │
│  - OpenAI / DeepSeek / Claude 等        │
└─────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 具体实践 |
|------|---------|
| **前后端分离** | 前端纯静态 SPA，后端无状态 API 服务 |
| **无状态服务** | FastAPI 不保存会话状态，全部存在 JWT Token 中 |
| **异步优先** | 所有 LLM 调用走 Celery 队列，HTTP 层只负责任务派发 |
| **数据隔离** | 所有数据库查询必须带 `owner_id` 或 `project_id` 过滤 |
| **配置即代码** | 环境变量管理所有可变配置，代码中无硬编码 |

---

## 2. 技术栈选型与理由

### 2.1 后端技术栈

| 技术 | 版本 | 选型理由 |
|------|------|---------|
| **Python** | 3.12 | AI 生态最成熟，LLM SDK 原生支持 |
| **FastAPI** | 0.115 | 异步原生、自动生成 OpenAPI 文档、类型提示完善 |
| **SQLAlchemy 2.0** | 2.0.36 | ORM 行业标准，原生异步会话 |
| **asyncpg** | 0.30 | PostgreSQL 异步驱动，性能接近原生 |
| **Alembic** | 1.14 | 官方迁移工具，支持自动迁移 |
| **Pydantic** | 2.9 | 数据校验与序列化，FastAPI 深度集成 |
| **Celery** | 5.4 | Python 最成熟分布式任务队列 |
| **Redis** | 7 | Celery broker + 结果后端 |
| **PostgreSQL** | 16 | JSONB、全文搜索、事务完整 |
| **httpx** | 0.27 | 异步 HTTP 客户端 |
| **python-jose** | 3.3 | JWT 编码/解码 |
| **passlib** | 1.7 | bcrypt 密码哈希 |
| **cryptography** | 42+ | Fernet 对称加密 |

### 2.2 前端技术栈

| 技术 | 版本 | 选型理由 |
|------|------|---------|
| **React** | 18.3 | 组件化、生态最丰富 |
| **TypeScript** | 5.6 | 类型安全 |
| **Vite** | 5.4 | 构建速度快 |
| **Tailwind CSS** | 3.4 | 原子化 CSS，快速构建设计系统 |
| **React Query** | 5.61 | 服务端状态管理（缓存、重试、去重） |
| **Zustand** | 5.0 | 轻量全局状态 |
| **React Router** | 6.28 | 声明式路由 |
| **Axios** | 1.7 | 拦截器、错误处理 |

### 2.3 不选其他方案的理由

| 候选方案 | 放弃理由 |
|---------|---------|
| Django | 同步框架，不适合高并发 LLM 代理 |
| Flask | 无原生异步支持 |
| Node.js/NestJS | Python AI 生态更成熟 |
| Vue.js | 团队 React 经验更丰富 |
| RQ/Dramatiq | Celery 生态最完善 |
| MongoDB | 关系型数据为主，PostgreSQL JSONB 足够 |

---

## 3. 后端架构详解

### 3.1 六层架构约束

```
HTTP 请求
    │
    ▼
┌─────────────┐    Router 层：参数校验、权限检查、调用 Service
│   Router    │    禁止：写业务逻辑、直接操作数据库
└──────┬──────┘
       │
       ▼
┌─────────────┐    Service 层：业务逻辑编排
│   Service   │    禁止：写 HTTP 逻辑
└──────┬──────┘
       │
       ▼
┌─────────────┐    Infra 层：数据库/Redis/向量库
│    Infra    │    禁止：写业务逻辑
└──────┬──────┘
       │
       ▼
┌─────────────┐    Core 层：配置、安全工具
│    Core     │
└─────────────┘
```

### 3.2 依赖注入示例

```python
# routers/generate.py
@router.post("/projects/{id}/generate/architecture")
async def generate_architecture(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await project_service.get_project_by_id(
        db, project_id, current_user.id
    )
    if not project:
        raise HTTPException(404, "项目不存在")
    
    task = await task_service.create_task(
        db, project_id, "architecture", current_user.id
    )
    run_architecture.delay(str(task.id))  # 异步派发
    return {"task_id": task.id}
```

---

## 4. 前端架构详解

### 4.1 状态管理策略

| 状态类型 | 管理方案 | 理由 |
|---------|---------|------|
| 服务端状态 | React Query | 缓存、去重、自动刷新 |
| 全局客户端状态 | Zustand | 轻量、无样板代码 |
| 局部 UI 状态 | useState | 简单直接 |

### 4.2 数据流

```
用户操作 → API 调用 → Axios 拦截器 → React Query → 后端 API → invalidate Queries → 自动刷新
```

---

## 5. 核心功能技术实现

### 5.1 认证系统

```
注册 → bcrypt 哈希 → 写入 users 表
登录 → 校验 bcrypt → 生成 JWT (HS256, 24h) → 前端存储
请求 → Authorization Header → JWT 解码 → 注入 current_user
```

### 5.2 小说生成流水线

**架构生成（5 步递进）：**

```python
async def generate_architecture(project, llm_config):
    hook = await _invoke_llm(hook_prompt, llm_config)
    world_view = await _invoke_llm(world_view_prompt.format(hook=hook), llm_config)
    plot = await _invoke_llm(plot_prompt.format(world_view=world_view), llm_config)
    characters = await _invoke_llm(character_prompt.format(plot=plot), llm_config)
    outline = await _invoke_llm(outline_prompt.format(characters=characters), llm_config)
    return combine_results(hook, world_view, plot, characters, outline)
```

每步传递上文，确保后续生成基于前文。

### 5.3 短剧改编流水线

```python
async def generate_drama_script(outline, chapters_text, characters, context_scripts, llm_config):
    context_summary = build_context_summary(context_scripts)  # 续集记忆
    prompt = script_prompt.format(
        outline=json.dumps(outline),
        chapters_text=truncate(chapters_text, 3000),
        characters=characters,
        context_summary=context_summary,
    )
    raw = await _invoke_llm(prompt, max_tokens=12000, llm_config=llm_config)
    return parse_json(raw)  # {scenes: [{shots: [{dialogue, camera, audio}]}]}
```

---

## 6. 数据模型设计

### 6.1 核心 ER 关系

```
users ──► projects ──► chapters
            │
            ├──► project_assets (architecture/directory/characters/world_state/drama_plan)
            ├──► tasks (pending/running/success/failed)
            └──► drama_episodes (outline_json/script_json)
```

### 6.2 关键表

**projects：**
```python
class Project(Base):
    name: Mapped[str]
    topic: Mapped[str | None]     # 主题
    genre: Mapped[str | None]     # 类型（修仙/都市/玄幻）
    num_chapters: Mapped[int]
    word_number: Mapped[int]
    owner_id: Mapped[str]         # 数据隔离关键
    status: Mapped[str]           # draft/generating/completed
```

**project_assets（半结构化资产）：**
```python
class ProjectAsset(Base):
    project_id: Mapped[str]
    asset_type: Mapped[str]       # architecture/directory/characters/world_state
    content_text: Mapped[str | None]   # 文本内容
    content_json: Mapped[dict | None]  # JSON 内容（PostgreSQL JSONB）
    version: Mapped[int]          # 版本号，支持回溯
```

**tasks：**
```python
class Task(Base):
    project_id: Mapped[str]
    task_type: Mapped[str]        # architecture/directory/chapter/drama_plan/drama_episode
    status: Mapped[str]           # pending/running/success/failed
    progress: Mapped[int]         # 0-100
    params: Mapped[dict | None]   # 任务参数
    result: Mapped[dict | None]   # 执行结果
    error_msg: Mapped[str | None] # 错误信息
```

---

## 7. AI/LLM 集成架构

### 7.1 Adapter 模式

```python
class LLMAdapter:
    """统一接口，支持任意 OpenAI-Compatible API"""
    
    def __init__(self, base_url: str, api_key: str, model: str, 
                 temperature: float = 0.7, max_tokens: int = 2048):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **kwargs
        )
        return response.choices[0].message.content
```

### 7.2 配置解析链

```python
def resolve_llm_config(user_config: dict | None = None) -> dict:
    """
    优先级：用户项目配置 > 用户全局配置 > 平台默认配置
    """
    base = {
        "interface_format": settings.LLM_INTERFACE_FORMAT,
        "base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
        "api_key": settings.LLM_API_KEY,
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": settings.LLM_MAX_TOKENS,
    }
    
    if user_config:
        for key in base:
            if user_config.get(key):
                base[key] = user_config[key]
    
    if base.get("api_key"):
        base["api_key"] = decrypt_key(base["api_key"])  # Fernet 解密
    
    return base
```

### 7.3 重试与容错

```python
async def _invoke_with_retry(adapter: LLMAdapter, prompt: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            response = await adapter.generate(prompt)
            return clean_output(response)
        except (TimeoutError, RateLimitError):
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 指数退避
```

---

## 8. 异步任务引擎

### 8.1 Celery 配置

```python
celery_app = Celery(
    "ai_novel_studio",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=3600,       # 1 小时超时
    worker_prefetch_multiplier=1,  # 公平分发
)
```

### 8.2 任务定义

```python
@celery_app.task(bind=True)
def run_architecture(self, task_id: str):
    asyncio.run(_run_with_cleanup(run_architecture_task(UUID(task_id))))

@celery_app.task(bind=True)
def run_chapter(self, task_id: str):
    asyncio.run(_run_with_cleanup(run_chapter_task(UUID(task_id))))
```

### 8.3 asyncio + Celery 兼容

**核心问题：** Celery Worker 是同步进程，业务代码是 async。

**解决方案：** `asyncio.run()` + 连接池释放。

```python
async def _run_with_cleanup(coro):
    try:
        await coro
    finally:
        try:
            await engine.dispose()  # 关键：释放 asyncpg 连接
        except Exception:
            pass
```

### 8.4 前端轮询

```typescript
const pollTask = (taskId, onSuccess, onError, onProgress): (() => void) => {
  const interval = setInterval(async () => {
    const task = await getTask(taskId);
    onProgress?.(task.progress, task.status);
    
    if (task.status === "success") {
      clearInterval(interval);
      onSuccess();
    } else if (task.status === "failed") {
      clearInterval(interval);
      onError?.(task.error_msg);
    }
  }, 3000);
  
  return () => clearInterval(interval);  // 返回清理函数
};
```

---

## 9. 世界状态系统（核心壁垒）

### 9.1 系统架构

```
章节正文生成
    │
    ▼
extract_world_state_delta()  ──► LLM 提取角色/事件/世界变更
    │
    ▼
merge_world_state()          ──► 合并到 world_state，记录变更历史
    │
    ▼
build_state_summary()        ──► 筛选与下一章相关的状态点
    │
    ▼
注入下一章 Prompt            ──► world_state_summary 加入上下文
```

### 9.2 Genre Template

```python
XIANXIA_TEMPLATE = {
    "characters": {
        "fields": ["realm", "cultivation_method", "magic_treasures", 
                   "skills", "physical_state", "mental_state"],
    },
    "events": {
        "fields": ["event_type", "participants", "consequences", "location"],
    },
    "world": {
        "fields": ["location_rules", "power_structure", "hidden_forces", 
                   "time_line", "special_rules"],
    },
}

def get_template(genre: str) -> dict:
    genre_lower = genre.lower()
    if any(k in genre_lower for k in ["仙", "玄", "武", "修", "魔", "神"]):
        return XIANXIA_TEMPLATE
    elif any(k in genre_lower for k in ["都", "现", "商", "职", "系"]):
        return URBAN_TEMPLATE
    return GENERIC_TEMPLATE
```

### 9.3 状态合并算法

```python
def merge_world_state(old_state: dict, delta: dict) -> dict:
    import copy
    state = copy.deepcopy(old_state)
    delta_copy = copy.deepcopy(delta)
    
    history_entry = {"chapter": delta_copy.pop("changed_in_chapter"), "changes": []}
    
    for category in ["characters", "events", "world"]:
        for key, fields in delta_copy.get(category, {}).items():
            old_entry = state.get(category, {}).get(key, {})
            for field, new_value in fields.items():
                old_value = old_entry.get(field)
                if old_value != new_value:
                    history_entry["changes"].append({
                        "category": category, "key": key,
                        "field": field, "old": old_value, "new": new_value,
                    })
                    state.setdefault(category, {}).setdefault(key, {})[field] = new_value
    
    state.setdefault("history", []).append(history_entry)
    return state
```

---

## 10. 安全架构

### 10.1 四层安全

```
Layer 1: 传输安全 ──► HTTPS + CORS 白名单
Layer 2: 认证安全 ──► JWT (HS256, 24h) + bcrypt (work_factor=12)
Layer 3: 授权安全 ──► 项目级数据隔离，所有查询带 owner_id
Layer 4: 数据安全 ──► API Key Fernet 加密，敏感信息不出现在日志
```

### 10.2 API Key 加密

```python
from cryptography.fernet import Fernet

fernet = Fernet(settings.FERNET_SECRET.encode())

def encrypt_key(plain_key: str) -> str:
    return fernet.encrypt(plain_key.encode()).decode()

def decrypt_key(encrypted_key: str) -> str:
    return fernet.decrypt(encrypted_key.encode()).decode()
```

---

## 11. 部署与运维架构

### 11.1 生产部署

```
GitHub
    ├──► Vercel (前端 CDN)
    └──► Render / VPS (后端 Docker)
            └── Supervisor
                    ├── FastAPI (端口 8000)
                    └── Celery Worker
```

### 11.2 Docker + Supervisor

```dockerfile
# 多阶段构建
FROM python:3.12-slim as builder
RUN pip install --user -r requirements.txt

FROM python:3.12-slim
RUN apt-get install -y libpq5 supervisor
COPY --from=builder /root/.local /root/.local
COPY supervisord.conf /etc/supervisor/conf.d/

CMD bash -c "alembic upgrade head && /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf"
```

```ini
[program:fastapi]
command=uvicorn app.main:app --host 0.0.0.0 --port 8000
autostart=true
autorestart=true

[program:celery]
command=celery -A app.worker.tasks worker --loglevel=info --pool=solo
autostart=true
autorestart=true
```

---

## 12. 性能与扩展性

### 12.1 当前性能

| 操作 | 耗时 |
|------|------|
| 架构生成（5 步） | ~260s |
| 目录生成 | ~60s |
| 单章生成 | ~60-120s |
| 短剧脚本 | ~180s |
| 世界状态提取 | ~30s |

### 12.2 扩展路径

| 瓶颈 | 当前 | 扩展方案 |
|------|------|---------|
| 单 Worker | 1 个 | 增加 Worker 进程/机器 |
| 数据库 | 单 PostgreSQL | 读写分离 |
| LLM 限流 | 单提供商 | 多模型负载均衡 |
| 向量存储 | 本地 Chroma | Qdrant 云向量库 |

---

## 13. 测试策略

| 测试类型 | 覆盖范围 | 工具 |
|---------|---------|------|
| 单元测试 | Service 核心逻辑 | pytest |
| 集成测试 | API 端到端 | pytest + TestClient |
| 前端测试 | 组件渲染 | Vitest |
| E2E 测试 | 完整用户流程 | Playwright |

现有测试：`backend/app/tests/test_world_state.py` — 21 个用例全部通过。

---

## 14. 技术债务与演进

| 债务项 | 影响 | 解决计划 |
|--------|------|---------|
| 单 Worker | 并发受限 | Phase 2 增加 Worker |
| 无 WebSocket | 需轮询 | Phase 3 引入推送 |
| Chroma 本地 | 多实例不一致 | Phase 3 迁移 Qdrant |
| 无限流 | 被刷 API 风险 | Phase 2 增加限流 |

---

## 附录：代码量统计

| 模块 | 文件数 | 代码行数 |
|------|--------|---------|
| 后端核心 | 35+ | ~6,000 |
| 前端核心 | 40+ | ~8,000 |
| Prompt 模板 | 15+ | ~3,000 |
| 测试 | 1 | ~300 |
| 文档 | 8 | ~5,000 |
| **总计** | **100+** | **~22,000** |

---

*文档版本：v1.0 | 更新日期：2026-05-10*
