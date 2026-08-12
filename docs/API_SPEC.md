# API 接口规范

## 概述

- 基础路径：所有 API 以 `/api/v1` 为前缀（MVP 阶段可省略版本号，直接以根路径暴露）
- 认证方式：JWT Bearer Token
- 内容类型：`application/json`
- 时区：UTC

## 通用响应格式

### 成功响应

```json
{
  "data": {},
  "message": "success"
}
```

### 错误响应

```json
{
  "detail": "错误描述"
}
```

## 接口清单

### 认证

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /auth/register | 用户注册 | 已实现 |
| POST | /auth/login | 用户登录 | 已实现 |
| GET | /auth/me | 当前用户信息 | 已实现 |

**请求/响应示例**

注册：
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "testpass123"
}
```

响应：
```json
{
  "id": "99e2da04-d726-4b5f-a19f-0bcd3e72fe3e",
  "username": "testuser",
  "email": "test@example.com"
}
```

登录：
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "testuser",
  "password": "testpass123"
}
```

响应：
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

当前用户：
```http
GET /api/auth/me
Authorization: Bearer <token>
```

响应：
```json
{
  "id": "99e2da04-d726-4b5f-a19f-0bcd3e72fe3e",
  "username": "testuser",
  "email": "test@example.com"
}
```

### 用户设置

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /user/llm-config | 获取当前用户 LLM 配置 | 已实现 |
| PUT | /user/llm-config | 更新用户 LLM 配置 | 已实现 |
| POST | /user/llm-config/test | 测试 LLM 配置连接 | 已实现 |

**请求/响应示例**

获取配置：
```http
GET /api/user/llm-config
Authorization: Bearer <token>
```

响应：
```json
{
  "api_key": "sk-xxxxxxxx",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-chat",
  "source": "user_custom"
}
```

更新配置：
```http
PUT /api/user/llm-config
Content-Type: application/json
Authorization: Bearer <token>

{
  "api_key": "sk-new-key",
  "base_url": "https://custom.api.com/v1",
  "model": "custom-model"
}
```

> `api_key` 传 `null` 或省略表示不修改；传空字符串 `""` 表示清除自定义 Key，恢复平台默认。

测试连接：
```http
POST /api/user/llm-config/test
Content-Type: application/json
Authorization: Bearer <token>

{
  "api_key": "sk-test-key",
  "base_url": "https://custom.api.com/v1",
  "model": "custom-model"
}
```

响应：
```json
{
  "success": true,
  "message": "连接成功，模型响应: Hello"
}
```

### 项目

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /projects | 项目列表 | 已实现 |
| POST | /projects | 创建项目 | 已实现 |
| GET | /projects/{id} | 项目详情 | 已实现 |
| PUT | /projects/{id} | 更新项目 | 已实现 |
| DELETE | /projects/{id} | 删除项目 | 已实现 |

**请求/响应示例**

创建项目：
```http
POST /api/projects
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "测试小说",
  "topic": "修真世界",
  "genre": "玄幻",
  "num_chapters": 50,
  "word_number": 3000,
  "story_shape": "final"
}
```

- `story_shape` **必填**（final / open），缺失或取值非法 → 422。
- `story_shape='open'`（连载开篇）时 `total_chapters_target` **必填**：10 ≤ M ≤ 1000 且 M > num_chapters，违反 → 422。
- `story_shape='final'`（短篇完结）时不允许携带 `total_chapters_target`（携带 → 422）。

响应：
```json
{
  "id": "a4c0e0e7-5bea-4e61-9ffb-95d901feebc7",
  "name": "测试小说",
  "topic": "修真世界",
  "genre": "玄幻",
  "num_chapters": 50,
  "word_number": 3000,
  "story_shape": "final",
  "total_chapters_target": null,
  "owner_id": "7d1f7bc7-7c75-4ed4-a55f-0c2a9963fd18",
  "status": "draft",
  "created_at": "2026-05-05T11:37:45.888222Z",
  "updated_at": "2026-05-05T11:37:45.888222Z"
}
```

列表项目：
```http
GET /api/projects
Authorization: Bearer <token>
```

响应：
```json
[
  {
    "id": "a4c0e0e7-5bea-4e61-9ffb-95d901feebc7",
    "name": "测试小说",
    "topic": "修真世界",
    "genre": "玄幻",
    "num_chapters": 50,
    "word_number": 3000,
    "story_shape": "final",
    "total_chapters_target": null,
    "owner_id": "7d1f7bc7-7c75-4ed4-a55f-0c2a9963fd18",
    "status": "draft",
    "created_at": "2026-05-05T11:37:45.888222Z",
    "updated_at": "2026-05-05T11:37:45.888222Z"
  }
]
```

更新项目：
```http
PUT /api/projects/{id}
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "测试小说（改）",
  "story_shape": "open",
  "total_chapters_target": 200
}
```

- `total_chapters_target` **创建后不可修改**：已锁定 M 的项目传入不同 M → 400「全书目标章数创建后不可修改」。
- `story_shape` 可修改：`open→final` 自动清空 M（服务端将 M 置 NULL）；`final→open` 必须补传 `total_chapters_target`（缺失 → 400）。

> 所有项目接口均通过 `get_current_user` 依赖验证 JWT，并严格按 `owner_id` 隔离数据。非 owner 访问返回 404。

### 小说生成

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /projects/{id}/generate/architecture | 生成架构（真实 LLM）；可选 body `{"guidance": "..."}` 优化提示词 | 已实现 |
| POST | /projects/{id}/generate/directory | 生成目录（真实 LLM）；可选 body `{"guidance": "..."}` 优化提示词 | 已实现 |
| POST | /projects/{id}/generate/chapter/{num} | 生成章节（真实 LLM） | 已实现 |
| POST | /projects/{id}/generate/drama-plan | 生成短剧改编计划（任务桩） | 已实现 |
| POST | /projects/{id}/generate/drama-episode/{num} | 生成短剧单集脚本（支持 chapter_nums 选择） | 已实现 |
| POST | /projects/{id}/generate/continue-writing | 续写（open 形态）：body `{"chapters": k}`，追加目录（正文由章节页批量生成） | 已实现 |
| POST | /projects/{id}/finalize/chapter/{num} | 定稿章节 | 待实现 |
| POST | /projects/{id}/generate/batch | 批量生成 | 待实现 |

**请求/响应示例**

生成架构（优化重新生成：携带 guidance 与当前全文快照）：
```http
POST /api/projects/{id}/generate/architecture
Content-Type: application/json
Authorization: Bearer <token>

{
  "guidance": "侧重群像，压缩世界观铺垫"
}
```

- `guidance` 可选；超过 2000 字返回 400。未传 body 时按空提示词处理，行为与旧版一致。
- 提交时服务端自动从资产表取当前版本全文作为快照，连同 `guidance` 一并写入 `task.params.user_guidance` / `task.params.current_content`，供 worker 做「优化重新生成」与版本历史记录。

续写（open 形态，追加 N+1 ~ N+k 章）：
```http
POST /api/projects/{id}/generate/continue-writing
Content-Type: application/json
Authorization: Bearer <token>

{
  "chapters": 10
}
```

- 仅 `story_shape='open'` 可续写，非 open → 400「仅连载开篇（open）形态项目可续写」。
- `chapters`（k）必须为正整数，k < 1 → 422。
- 已锁定全书目标 M 且 `num_chapters + k > M` → 422（提示剩余可续写章数）。
- 任务 `task_type='continue_writing'`：两步串行——更新 num_chapters → 追加目录（`_ensure_chapters(skip_existing=True)`，不覆盖已有定稿，目录资产累积落库）；**不生成正文**（正文由章节页 `batch_chapters`「AI 批量生成」确认目录后触发，增量语义跳过已有 draft）；成功返回 TaskOut，前台轮询 `GET /tasks/{id}`。

响应（创建任务）：
```json
{
  "id": "t1a2b3c4-...",
  "project_id": "a4c0e0e7-...",
  "task_type": "continue_writing",
  "status": "pending",
  "params": {
    "project_id": "a4c0e0e7-...",
    "chapters": 10
  },
  "result": null,
  "progress": 0,
  "error_msg": null,
  "created_at": "2026-08-12T00:00:00Z",
  "updated_at": "2026-08-12T00:00:00Z"
}
```

响应（创建任务）：
```json
{
  "id": "t1a2b3c4-...",
  "project_id": "a4c0e0e7-...",
  "task_type": "architecture",
  "status": "pending",
  "params": {
    "project_id": "a4c0e0e7-...",
    "user_guidance": "侧重群像，压缩世界观铺垫",
    "current_content": "…当前版本架构全文…"
  },
  "result": null,
  "progress": 0,
  "error_msg": null,
  "created_at": "2026-05-05T12:00:00Z",
  "updated_at": "2026-05-05T12:00:00Z"
}
```

> architecture / directory / chapter 均已接入真实 LLM 生成。创建任务后立即返回 `task_id`，后台通过 **Celery** 异步执行，状态流转：pending → running → success / failed。支持通过 `POST /tasks/{task_id}/cancel` 取消运行中任务。chapter 生成依赖前置资产：需先完成 architecture 和 directory 生成。

### 章节

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /projects/{id}/chapters | 章节列表 | 已实现 |
| POST | /projects/{id}/chapters | 创建章节 | 已实现 |
| GET | /chapters/{id} | 章节详情 | 已实现 |
| PUT | /chapters/{id} | 更新章节 | 已实现 |
| DELETE | /chapters/{id} | 删除章节 | 已实现 |

**请求/响应示例**

创建章节：
```http
POST /api/projects/{id}/chapters
Content-Type: application/json
Authorization: Bearer <token>

{
  "chapter_num": 1,
  "title": "第一章 初入宗门",
  "outline": "主角被测出废灵根，却意外获得神秘玉佩...",
  "draft": "",
  "finalized_text": "",
  "status": "draft"
}
```

响应：
```json
{
  "id": "c1a2e3b4-...",
  "project_id": "a4c0e0e7-...",
  "chapter_num": 1,
  "title": "第一章 初入宗门",
  "outline": "主角被测出废灵根，却意外获得神秘玉佩...",
  "draft": "",
  "finalized_text": "",
  "status": "draft",
  "version": 1,
  "created_at": "2026-05-05T12:00:00Z",
  "updated_at": "2026-05-05T12:00:00Z"
}
```

> 章节接口通过 `project_id` 关联到项目，所有权校验与项目接口一致（非 owner 返回 404）。

### 内容编辑（资产读写）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /projects/{id}/assets/{type} | 获取资产 | 已实现 |
| PUT | /projects/{id}/assets/{type} | 更新资产（architecture/directory 追加 trigger=manual 历史行） | 已实现 |
| GET | /projects/{id}/assets/{type}/versions | 版本历史列表（按 version 倒序） | 已实现 |
| POST | /projects/{id}/assets/{type}/rollback | 回滚到指定版本（body `{"version": N}`） | 已实现 |

**请求/响应示例**

获取资产：
```http
GET /api/projects/{id}/assets/architecture
Authorization: Bearer <token>
```

响应：
```json
{
  "id": "...",
  "project_id": "...",
  "asset_type": "architecture",
  "content_text": "世界观：修仙大陆，灵气复苏...",
  "content_json": null,
  "version": 1,
  "updated_at": "2026-05-05T12:00:00Z"
}
```

更新资产：
```http
PUT /api/projects/{id}/assets/architecture
Content-Type: application/json
Authorization: Bearer <token>

{
  "content_text": "世界观：修仙大陆，灵气复苏...",
  "content_json": {"world_rules": [...]}
}
```

> 对 `architecture` / `directory` 保存会追加一条 `trigger_type="manual"` 的版本历史行（version 取保存后当前版本号）。

版本历史列表：
```http
GET /api/projects/{id}/assets/architecture/versions
Authorization: Bearer <token>
```

响应（按 version 倒序）：
```json
[
  {
    "id": "...",
    "version": 3,
    "trigger_type": "manual",
    "guidance": null,
    "created_at": "2026-08-11T00:00:00Z"
  },
  {
    "id": "...",
    "version": 2,
    "trigger_type": "generate",
    "guidance": "侧重群像",
    "created_at": "2026-08-11T00:00:00Z"
  }
]
```

回滚：
```http
POST /api/projects/{id}/assets/architecture/rollback
Content-Type: application/json
Authorization: Bearer <token>

{
  "version": 2
}
```

- `version` 必须为正整数；非数字 / 布尔 / < 1 返回 400。
- 目标版本不存在返回 404；成功把该版本全文写回当前资产（version 续 +1，追加 `trigger_type="rollback"` 历史行），响应为当前资产结构（同 GET 资产）。

**asset_type 枚举**：architecture, directory, characters, settings, drama_plan, world_state, arc_summaries, foreshadowing

### 短剧改编

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /projects/{id}/generate/drama-plan | 生成改编计划（任务桩） | 已实现 |
| POST | /projects/{id}/generate/drama-episode/{num} | 生成单集脚本（任务桩） | 已实现 |
| GET | /projects/{id}/drama-episodes | 短剧集列表 | 已实现 |
| GET | /drama/episodes/{ep_id}/script | 分镜脚本 | 待实现 |
| GET | /drama/episodes/{ep_id}/export?format=json\|md\|csv | 导出单集脚本 | 已实现 |
| POST | /drama/episodes/export/batch | 批量导出选中剧集脚本 | 已实现 |
| PUT | /drama/episodes/{ep_id}/outline | 更新剧集大纲 | 已实现 |
| PUT | /drama/episodes/{ep_id}/script | 更新剧集脚本 | 已实现 |
| PUT | /drama/episodes/{ep_id}/source-chapters | 更新来源章节映射 | 已实现 |
| POST | /api/chapters/export/batch | 批量导出选中章节 | 已实现 |

### AI 问答

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /projects/{id}/chat-sessions | 获取项目的会话列表 | 已实现 |
| GET | /chat-sessions | 获取当前用户的全部会话列表 | 已实现 |
| POST | /chat-sessions | 创建新会话 | 已实现 |
| GET | /chat-sessions/{session_id} | 获取会话详情（含消息） | 已实现 |
| POST | /chat-sessions/{session_id}/messages | 发送消息，返回 AI 回复 | 已实现 |

**请求/响应示例**

创建会话：
```http
POST /api/chat-sessions
Content-Type: application/json
Authorization: Bearer <token>

{
  "project_id": "...",
  "title": "角色讨论"
}
```

发送消息：
```http
POST /api/chat-sessions/{session_id}/messages
Content-Type: application/json
Authorization: Bearer <token>

{
  "content": "帮我完善这个角色设定"
}
```

响应（AI 回复）：
```json
{
  "id": "...",
  "session_id": "...",
  "role": "assistant",
  "content": "好的，让我们从角色的核心动机开始...",
  "model_name": "deepseek-chat",
  "tokens_used": 256,
  "created_at": "2026-05-09T12:00:00Z",
  "updated_at": "2026-05-09T12:00:00Z"
}
```

### 创作灵感

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /inspiration/categories | 预设灵感分类列表 | 已实现 |
| GET | /inspiration/hot | 热点灵感列表（按点赞排序） | 已实现 |
| POST | /projects/{id}/inspiration | 导入灵感（设主题 + 写入 inspiration 资产） | 已实现 |

**请求/响应示例**

获取分类（需 JWT）：
```http
GET /api/inspiration/categories
Authorization: Bearer <token>
```

响应：
```json
[
  "热门话题",
  "小说推荐",
  "短剧",
  "玄幻",
  "重生"
]
```

获取热点（需 JWT）：
```http
GET /api/inspiration/hot?category=玄幻&keyword=重生&limit=20
Authorization: Bearer <token>
```

响应：
```json
[
  {
    "note_id": "662f00000000000000000000",
    "title": "重生之我在都市当神豪",
    "summary": "主角重生九十年代逆袭……",
    "likes": 5200,
    "collects": 320,
    "url": "https://example.com/note/662f00000000000000000000",
    "author": "某作者",
    "fetched_at": "2026-08-04T06:30:00Z"
  }
]
```

> 说明：
> - 三个灵感接口均通过 `get_current_user` 依赖验证 JWT，鉴权方式与项目接口一致。
> - `GET /api/inspiration/hot` 仅返回最近一批采集的热点（`fetched_at` 为最新批次），按 `likes` 降序排列；支持 `category`（精确匹配）与 `keyword`（对标题/摘要模糊搜索）过滤，`limit` 默认 20、上限 50。
> - 热点响应字段为 note_id / title / summary / likes / collects / url / author / fetched_at，**不含 source 字段**。
> - `POST /api/projects/{id}/inspiration` 请求体为灵感对象（note_id / title / summary / likes / url / author / tags）。导入会将项目 `topic` 设为标题，并把灵感详情写入 `inspiration` 资产（幂等覆盖，重复导入覆盖旧内容）。项目不存在或非 owner 返回 404。

导入灵感（需 JWT）：
```http
POST /api/projects/{id}/inspiration
Content-Type: application/json
Authorization: Bearer <token>

{
  "note_id": "662f00000000000000000000",
  "title": "重生之我在都市当神豪",
  "summary": "主角重生九十年代逆袭……",
  "likes": 5200,
  "url": "https://example.com/note/662f00000000000000000000",
  "author": "某作者",
  "tags": ["重生", "都市"]
}
```

响应：
```json
{
  "success": true,
  "topic": "重生之我在都市当神豪"
}
```

### 任务

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /projects/{id}/tasks | 创建任务 | 已实现 |
| GET | /projects/{id}/tasks | 任务列表 | 已实现 |
| GET | /tasks/{task_id} | 任务详情 | 已实现 |
| POST | /tasks/{task_id}/cancel | 取消任务 | 已实现 |
| POST | /tasks/{task_id}/retry | 重试任务 | 待实现 |

**请求/响应示例**

创建任务：
```http
POST /api/projects/{id}/tasks
Content-Type: application/json
Authorization: Bearer <token>

{
  "task_type": "architecture",
  "params": {"project_id": "..."}
}
```

查询任务：
```http
GET /api/tasks/{task_id}
Authorization: Bearer <token>
```

响应：
```json
{
  "id": "t1a2b3c4-...",
  "project_id": "...",
  "task_type": "architecture",
  "status": "pending",
  "params": {"project_id": "..."},
  "result": null,
  "progress": 0,
  "error_msg": null,
  "created_at": "2026-05-05T12:00:00Z",
  "updated_at": "2026-05-05T12:00:00Z"
}
```

### 系统

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | /health | 健康检查 | 已实现 |

## 开发约定

1. 新增接口必须在此文档中登记
2. 接口实现后更新"状态"列为"已实现"
3. 接口变更时同步更新请求/响应示例
