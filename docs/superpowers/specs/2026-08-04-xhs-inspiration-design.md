# 小红书创作灵感功能设计（V2）

- 日期：2026-08-04
- 状态：设计已批准
- 目标项目：`/Users/yxx/Desktop/novel_drama_v2`（本地 V2 开发版）

## 背景

创作者需要灵感来源。本项目（AI 小说 & 短剧创作工作台）希望为创作者提供每日热门话题/小说，作为创作方向和思路参考。

核心约束（用户明确要求）：
1. **采集与消费解耦**：小红书抓取在本机独立执行，V2 App 只读自己的数据库，运行时完全不依赖小红书/MCP。
2. **客户端不暴露来源**：前端/用户不知道热点数据来源于小红书。
3. **本地 V2 专用**：VPS 稳定版及部署流程不受影响。
4. **每日更新一次**：热点数据每天抓取一次写入数据库。

## 架构

```
┌─ 本地 Mac ───────────────────────────────────────┐
│ 【独立采集器】每天定时跑一次                       │
│  scripts/xhs_hot_collector.py                    │
│    ↓ MCP Streamable-HTTP → localhost:18060/mcp   │
│  search_feeds（预设分类 + 自定义关键词）           │
│    ↓ 按点赞排序 + 按 note_id 去重                 │
│  UPSERT → hot_topics 表（PostgreSQL）             │
└──────────────┬───────────────────────────────────┘
               │ （PostgreSQL 是唯一桥梁）
┌──────────────▼───────────────────────────────────┐
│ 【V2 App】只读自己的数据库，无 MCP/小红书依赖     │
│  GET  /api/inspiration/categories → 预设分类      │
│  GET  /api/inspiration/hot        → 读 hot_topics │
│  POST /api/projects/{id}/inspiration → 导入       │
└──────────────────────────────────────────────────┘
```

## 数据模型：`hot_topics` 表

新增 Alembic 迁移（`add_hot_topics_table`）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `category` | String | 预设分类（热门/小说/甜宠/…） |
| `note_id` | String, UNIQUE | 小红书笔记 ID，去重键 |
| `title` | String | 笔记标题 |
| `summary` | Text | 内容摘要（不用 `desc`——PostgreSQL 保留关键字） |
| `likes` | Integer | 点赞数（排序依据） |
| `collects` | Integer | 收藏数 |
| `shares` | Integer | 分享数 |
| `url` | String | 笔记链接 |
| `author` | String | 作者昵称 |
| `source` | String | 内部来源标记（如 `xiaohongshu`），**不返回给前端** |
| `fetched_at` | DateTime | 本次抓取时间 |
| `created_at` / `updated_at` | DateTime | 记录时间 |

**去重策略**：按 `note_id` UPSERT——同日重复抓取更新点赞数等字段；跨天保留同一笔记、刷新数据。API 只返回最近一次 `fetched_at` 批次的数据。

## 组件

### 1. 采集器 `scripts/xhs_hot_collector.py`（独立脚本）

- **不参与 Web 服务启动**，作为独立进程/定时任务运行。
- **MCP 客户端**：复用 `xhs-get/xhs-query-go/mcp_client.py` 的 MCP Streamable-HTTP 协议（JSON-RPC 2.0 + `Mcp-Session-Id`），用同步 `requests` 实现（采集器独立于 FastAPI 异步环境）。含限速（0.8s/请求）+ 重试。
- **预设分类 → 关键词映射**：内置配置（32 个分类，见下方「预设分类清单」），可在脚本配置中调整。采集器对每个分类的每个关键词执行 `search_feeds`。
- **流程**：对每个分类的每个关键词 → `search_feeds` → 收集 feeds → 合并 → 按点赞数排序 → 取每分类 Top N（默认 20）→ 按 `note_id` UPSERT 到 `hot_topics`。
- **定时**：macOS launchd plist（每天固定时间，如 08:00）或 `crontab`；支持手动 `python scripts/xhs_hot_collector.py` 立即执行。
- **依赖**：`requests`、`psycopg2-binary`（或复用 SQLAlchemy 连接）。

### 2. V2 后端（3 个新文件，全部读 DB，零 MCP 依赖）

- `backend/app/routers/inspiration.py`：
  - `GET /api/inspiration/categories` → 预设分类列表（从配置读取，可选从 DB 去重取）
  - `GET /api/inspiration/hot?category=&limit=` → 读 `hot_topics`，按 `fetched_at` 取最近批次 + 按 `likes` 排序
  - `POST /api/projects/{id}/inspiration` → **一键导入**（见下）
- `backend/app/services/inspiration_service.py`：
  - `get_hot_notes(category, limit)` — 查询 DB
  - `import_inspiration(project_id, note)` — 设 `projects.topic` + 写 `project_assets`（`asset_type='inspiration'`，存 JSON/文本）
- `backend/app/models/project.py` — 新增 `HotTopic` 模型

### 3. V2 前端 `frontend/src/pages/ProjectDetail/InspirationTab.tsx`

- 预设分类 chips + 自定义搜索框 + 刷新按钮
- 列表卡片：标题、👍点赞数、内容摘要、作者、链接
- 每条「导入项目」按钮 → 确认 → `POST /api/projects/{id}/inspiration` → toast
- 已导入的灵感单独展示（查看/替换）
- **文案中性**：界面用「创作灵感」「热门话题」，不出现「小红书」字样；`source` 字段不传给前端

### 4. 生成时参考

生成架构/目录时，后端读取项目已导入的 inspiration asset，把其摘要（title + desc + tags）**自动附加到 `user_guidance`** 注入 prompt。前端生成按钮无需改动。

## API 定义

| 方法 | 路径 | 请求 | 响应 |
|------|------|------|------|
| GET | `/api/inspiration/categories` | — | `["热门", "小说", "甜宠", ...]` |
| GET | `/api/inspiration/hot` | `?category=&limit=20` | `[{note_id, title, summary, likes, collects, url, author, fetched_at}]`（无 source） |
| POST | `/api/projects/{id}/inspiration` | `{note_id, title, summary, likes, url, author, tags?}` | `{success, topic}` |

所有接口走现有 JWT 鉴权（`get_current_user` + 项目 owner 隔离）。

## 错误处理

- 采集器：MCP 未连接/未登录 → 明确报错并退出（定时任务可跳过本次），不污染 DB
- 采集器：小红书限流/反爬 → 内置重试 + 限速；持续失败记录日志
- App：`hot_topics` 为空 → 返回空列表 + 提示「热点数据尚未更新，请先运行采集器」
- App 导入：项目不存在/非 owner → 404；重复导入同一灵感 → 幂等更新

## 测试

- 采集器：mock MCP 响应 → 验证解析、排序、UPSERT 去重
- 后端：`inspiration_service` 缓存/查询逻辑、导入接口（设 topic + 写 asset）
- 生成注入：有 inspiration asset 时 `user_guidance` 正确合并
- 前端：TypeScript 编译通过

## 环境变量 / 配置

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `XHS_MCP_URL` | 采集器连 MCP 地址 | `http://localhost:18060/mcp` |
| `DATABASE_URL` | 采集器连 V2 数据库 | 与 V2 后端一致 |
| `XHS_PRESET_CATEGORIES` | 预设分类→关键词 JSON（可选覆盖） | 内置默认 |

## 不在本次范围（Out of Scope）

- VPS 生产部署该功能
- 用户自定义采集任务 / 多小红书账号
- 热点数据的编辑/删除 UI
- 定时任务的 Web 化管理界面

## 预设分类清单（32 个）

调研自番茄小说/起点中文网热门分类与题材（2025）。采集器每天按这些分类抓取，前端 Tab 用**可横向滚动 chips + 「更多」下拉**承载。

**泛类（5）**

| 分类 | 关键词 |
|------|--------|
| 热门话题 | 热门 / 热搜 / 爆款 |
| 小说推荐 | 小说推荐 / 热门小说 / 书荒 |
| 短剧 | 短剧 / 短剧剧本 / 微短剧 |
| 影视改编 | 小说改编 / 影视化 / IP 改编 |
| 写作技巧 | 写作技巧 / 写小说 / 新手写作 |

**男频（14）**

| 分类 | 关键词 |
|------|--------|
| 玄幻 | 玄幻小说 / 玄幻 |
| 仙侠修仙 | 修仙小说 / 仙侠 / 长生 |
| 都市 | 都市小说 / 都市脑洞 |
| 重生 | 重生文 / 重生 |
| 穿越 | 穿越文 / 架空历史 |
| 历史权谋 | 历史小说 / 大明 / 三国 |
| 悬疑灵异 | 悬疑小说 / 灵异 / 惊悚 |
| 科幻末世 | 科幻小说 / 末世 / 无限流 |
| 系统流 | 系统流 / 面板流 / 签到 |
| 高武 | 高武 / 无敌流 |
| 游戏电竞 | 电竞小说 / 游戏文 |
| 军事战争 | 军事小说 / 军旅 |
| 武侠 | 武侠小说 / 江湖 |
| 同人二创 | 同人文 / 火影同人 / 斗罗同人 |

**女频（13）**

| 分类 | 关键词 |
|------|--------|
| 甜宠 | 甜宠文 / 甜文 |
| 现代言情 | 现代言情 / 都市言情 |
| 古代言情 | 古代言情 / 古言 |
| 豪门总裁 | 总裁文 / 豪门 / 霸总 |
| 宫斗宅斗 | 宫斗 / 宅斗 |
| 快穿 | 快穿文 |
| 娱乐圈 | 娱乐圈小说 / 顶流 |
| 校园青春 | 校园小说 / 青春 |
| 先婚后爱 | 先婚后爱 |
| 追妻火葬场 | 追妻火葬场 |
| 真假千金 | 真假千金 / 千金 |
| 萌宝 | 萌宝 / 团宠 / 奶爸 |
| 年代文 | 年代文 / 七零 / 八零 |

## 交付物清单

1. `backend/alembic/versions/*_add_hot_topics_table.py` + `HotTopic` 模型
2. `backend/app/services/inspiration_service.py` + `backend/app/routers/inspiration.py` + main.py 挂载
3. `scripts/xhs_hot_collector.py` + 预设分类配置 + launchd/cron 示例
4. `frontend/src/pages/ProjectDetail/InspirationTab.tsx` + api/inspiration.ts + ProjectDetail Tab 集成
5. 生成注入逻辑（`generation_service` / `task_service` 读取 inspiration asset）
6. 文档：CHANGELOG、API_SPEC 更新
