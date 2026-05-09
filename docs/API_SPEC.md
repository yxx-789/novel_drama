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
  "word_number": 3000
}
```

响应：
```json
{
  "id": "a4c0e0e7-5bea-4e61-9ffb-95d901feebc7",
  "name": "测试小说",
  "topic": "修真世界",
  "genre": "玄幻",
  "num_chapters": 50,
  "word_number": 3000,
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
    "owner_id": "7d1f7bc7-7c75-4ed4-a55f-0c2a9963fd18",
    "status": "draft",
    "created_at": "2026-05-05T11:37:45.888222Z",
    "updated_at": "2026-05-05T11:37:45.888222Z"
  }
]
```

> 所有项目接口均通过 `get_current_user` 依赖验证 JWT，并严格按 `owner_id` 隔离数据。非 owner 访问返回 404。

### 小说生成

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /projects/{id}/generate/architecture | 生成架构（真实 LLM） | 已实现 |
| POST | /projects/{id}/generate/directory | 生成目录（真实 LLM） | 已实现 |
| POST | /projects/{id}/generate/chapter/{num} | 生成章节（真实 LLM） | 已实现 |
| POST | /projects/{id}/generate/drama-plan | 生成短剧改编计划（任务桩） | 已实现 |
| POST | /projects/{id}/generate/drama-episode/{num} | 生成短剧单集脚本（支持 chapter_nums 选择） | 已实现 |
| POST | /projects/{id}/finalize/chapter/{num} | 定稿章节 | 待实现 |
| POST | /projects/{id}/generate/batch | 批量生成 | 待实现 |

**请求/响应示例**

生成架构：
```http
POST /api/projects/{id}/generate/architecture
Authorization: Bearer <token>
```

响应（创建任务）：
```json
{
  "id": "t1a2b3c4-...",
  "project_id": "a4c0e0e7-...",
  "task_type": "architecture",
  "status": "pending",
  "params": {"project_id": "a4c0e0e7-..."},
  "result": null,
  "progress": 0,
  "error_msg": null,
  "created_at": "2026-05-05T12:00:00Z",
  "updated_at": "2026-05-05T12:00:00Z"
}
```

> architecture / directory / chapter 均已接入真实 LLM 生成。创建任务后立即返回 `task_id`，后台通过 `asyncio.create_task` 异步执行，状态流转：pending → running → success。chapter 生成依赖前置资产：需先完成 architecture 和 directory 生成。

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
| PUT | /projects/{id}/assets/{type} | 更新资产 | 已实现 |

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

**asset_type 枚举**：architecture, directory, characters, settings, drama_plan

### 短剧改编

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /projects/{id}/generate/drama-plan | 生成改编计划（任务桩） | 已实现 |
| POST | /projects/{id}/generate/drama-episode/{num} | 生成单集脚本（任务桩） | 已实现 |
| GET | /projects/{id}/drama-episodes | 短剧集列表 | 已实现 |
| GET | /drama/episodes/{ep_id}/script | 分镜脚本 | 待实现 |
| GET | /drama/episodes/{ep_id}/export?format=json\|md\|csv | 导出单集脚本 | 已实现 |
| POST | /drama/episodes/export/batch | 批量导出选中剧集脚本 | 已实现 |
| POST | /api/chapters/export/batch | 批量导出选中章节 | 已实现 |

### 任务

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | /projects/{id}/tasks | 创建任务 | 已实现 |
| GET | /projects/{id}/tasks | 任务列表 | 已实现 |
| GET | /tasks/{task_id} | 任务详情 | 已实现 |
| POST | /tasks/{task_id}/cancel | 取消任务 | 待实现 |
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
