# 数据模型文档

## 设计原则

1. **MVP 优先简化**：不过度拆表，半结构化内容统一放入 `project_assets`
2. **扁平化设计**：短剧相关数据直接关联 `projects`，不引入中间 `drama_projects` 表
3. **环境变量优先**：平台级 LLM 配置通过 `backend/.env` 管理；用户级自定义配置存储在 `users` 表（加密），不单独建 `api_configs` 表
4. **可扩展**：预留版本字段，后续结构调整不影响现有数据

---

## 基类与公共字段

所有模型继承以下 Mixin：

- **UUIDMixin**：`id` (UUID, PK, default=uuid4)
- **TimestampMixin**：`created_at` / `updated_at` (DateTime(timezone=True), server_default=now(), onupdate=now())

---

## 核心表结构

### users

系统用户。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 用户唯一标识 |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 邮箱 |
| hashed_password | VARCHAR(255) | NOT NULL | bcrypt 哈希密码 |
| llm_api_key_encrypted | TEXT | nullable | Fernet 加密后的用户自定义 API Key |
| llm_base_url | VARCHAR(255) | nullable | 自定义 LLM base_url（空则继承平台默认） |
| llm_model | VARCHAR(100) | nullable | 自定义 LLM model（空则继承平台默认） |
| llm_config_updated_at | TIMESTAMPTZ | nullable | 配置更新时间 |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**索引**：email（登录查询）

**说明**：
- `llm_api_key_encrypted` 使用 Fernet 对称加密（256-bit AES + HMAC），解密密钥 `FERNET_SECRET` 从环境变量读取
- 用户未设置自定义配置时，所有 LLM 调用回退到平台默认（`settings.LLM_*`）
- 用户可只设置 `api_key` 而继承平台的 `base_url` 和 `model`

---

### projects

小说项目，一个项目对应一部长篇小说。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| name | VARCHAR(255) | NOT NULL | 项目名称 |
| topic | TEXT | | 小说主题 |
| genre | VARCHAR(100) | | 小说类型 |
| num_chapters | INTEGER | DEFAULT 0 | 计划章节数 |
| word_number | INTEGER | DEFAULT 0 | 计划每章字数 |
| owner_id | UUID | FK → users.id, NOT NULL | 项目创建者 |
| status | VARCHAR(20) | DEFAULT 'draft' | draft / generating / completed |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**索引**：owner_id（列表查询）

**说明**：
- MVP 阶段单人使用，owner_id 即为唯一用户
- Phase 2 引入 project_members 后才需要联表查询权限

---

### chapters

小说章节内容。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, NOT NULL | |
| chapter_num | INTEGER | NOT NULL | 章节序号 |
| title | VARCHAR(255) | | 章节标题 |
| outline | TEXT | | 章节大纲（生成时写入） |
| draft | TEXT | | 章节草稿（AI 生成） |
| finalized_text | TEXT | | 定稿正文（编辑后保存） |
| status | VARCHAR(20) | DEFAULT 'draft' | draft / draft_generated / generating / finalized |
| version | INTEGER | DEFAULT 1 | 乐观锁版本号 |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**唯一约束**：(project_id, chapter_num)
**索引**：project_id

**说明**：
- `outline`：生成目录时写入
- `draft`：生成章节草稿时写入
- `finalized_text`：定稿或用户手动编辑后写入
- `status` 流转：draft → draft_generated（AI 生成草稿）→ finalized（人工定稿）

---

### project_assets

半结构化项目资产，用于存储不单独拆表的内容。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, NOT NULL | |
| asset_type | VARCHAR(50) | NOT NULL | 资产类型 |
| content_text | TEXT | | 文本内容 |
| content_json | JSONB | | JSON 结构化内容 |
| version | INTEGER | DEFAULT 1 | |
| updated_by | UUID | FK → users.id | 最后修改人 |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**唯一约束**：(project_id, asset_type)
**索引**：project_id

**asset_type 枚举**（当前 `routers/assets.py` ASSET_TYPES 白名单）：

| 类型 | 内容说明 |
|------|---------|
| architecture | 小说架构（世界观、角色、情节蓝图） |
| directory | 章节目录 |
| characters | 结构化角色卡（`content_json` 双通道，P2-B） |
| settings | 世界观设定 |
| drama_plan | 短剧改编计划 |
| world_state | 世界状态（结构化记忆，P2-A） |
| arc_summaries | 记忆分层 L2/L3：`{arcs:[{arc_index,chapter_range,title,summary,frozen_at}], book_summary}`（P3-B：arc 摘要冻结不覆盖；L3 `book_summary` 在批量结束 / 单章最后一章各合成一次，写前在伏笔提醒命中时以【全书脉络】注入） |
| foreshadowing | 伏笔台账（纯规则，P3-B）：`{entries:[{name,note,added_chapter,last_touch_chapter,planned_recovery_range,status,subplot,known_by,tags}], unmatched}`；`known_by` 由写前【信息约束】消费（每章最近触碰 5 条 + 提醒命中伏笔），防角色说出不该知道的事 |

> 注：早期版本曾使用的 `character_state` / `global_summary` / `world_rule` / `timeline` / `adaptation_plan` 等类型已不在现行白名单，属历史遗留；`inspiration` 由灵感服务单独维护（不在 ASSET_TYPES 白名单内）。

---

### tasks

异步生成任务记录。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 任务唯一标识 |
| project_id | UUID | FK → projects.id, NOT NULL | |
| task_type | VARCHAR(50) | NOT NULL | 任务类型 |
| status | VARCHAR(20) | DEFAULT 'pending' | pending / running / success / failed |
| progress | INTEGER | DEFAULT 0 | 进度百分比 0-100 |
| params | JSONB | | 任务参数（如章节号等） |
| result | JSONB | | 任务结果（如 failed_chapters 列表） |
| error_msg | TEXT | | 失败原因 |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**索引**：project_id（按项目查询任务列表）

**task_type 枚举**：

| 类型 | 说明 |
|------|------|
| architecture | 生成小说架构 |
| directory | 生成章节目录 |
| chapter | 生成单章草稿 |
| batch_chapters | 批量生成章节 |
| drama_plan | 生成短剧改编计划 |
| drama_episode | 生成分集脚本 |
| drama_batch | 批量生成短剧脚本 |

**说明**：
- `params` 存储创建任务时传入的参数
- `result` 存储生成结果摘要（如 failed_chapters）
- 详细生成内容写入 chapters / project_assets / drama_episodes，不在 task 中冗余存储

---

### drama_episodes

短剧集（扁平化设计：直接关联 projects，不经过 drama_projects 中间表）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, NOT NULL | 来源小说项目 |
| episode_num | INTEGER | NOT NULL | 集数 |
| title | VARCHAR(255) | | 集标题 |
| source_chapters | VARCHAR(255) | | 来源章节号列表（逗号分隔） |
| outline_json | JSONB | | 本集大纲（hook / beats / cliffhanger） |
| script_json | JSONB | | 分镜头脚本数据 |
| status | VARCHAR(20) | DEFAULT 'pending' | pending / planned / outlined / script_ready |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**说明**：
- **扁平化决策**：MVP 阶段不单独创建 `drama_projects` 和 `drama_scripts` 表
- 所有短剧数据直接挂在 `projects` 下，通过 `drama_episodes` 存储集信息
- 脚本数据存储在 `script_json`（JSONB）中，避免为每集每场景单独建表
- `source_chapters` 记录该集改编所依据的小说章节

---

### chat_sessions

AI 问答会话。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, nullable | 关联项目（可为空，表示通用问答） |
| user_id | UUID | FK → users.id, NOT NULL | 会话所有者 |
| title | VARCHAR(255) | nullable | 会话标题（自动生成） |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**索引**：project_id, user_id

---

### chat_messages

AI 问答消息。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| session_id | UUID | FK → chat_sessions.id, NOT NULL | |
| role | VARCHAR(20) | NOT NULL | user / assistant / system |
| content | TEXT | NOT NULL | 消息内容 |
| model_name | VARCHAR(100) | nullable | 使用的模型名称 |
| tokens_used | INTEGER | nullable | 消耗的 token 数 |
| meta_json | JSONB | nullable | 扩展字段 |
| created_at | TIMESTAMPTZ | server_default=now() | |
| updated_at | TIMESTAMPTZ | server_default=now() | |

**索引**：session_id

---

## E-R 关系图

```
users ||--o{ projects : owns
users ||--o{ tasks : creates
users ||--o{ chat_sessions : owns

projects ||--o{ chapters : contains
projects ||--o{ project_assets : has
projects ||--o{ tasks : generates
projects ||--o{ drama_episodes : adapts_to
projects ||--o{ chat_sessions : has

chat_sessions ||--o{ chat_messages : contains
```

---

## 与旧项目数据映射

| 旧项目文件/数据 | 新模型表 | 字段/说明 |
|----------------|---------|---------|
| `Novel_architecture.txt` | `project_assets` | `asset_type='architecture'` |
| `Novel_directory.txt` | `project_assets` | `asset_type='directory'` |
| `character_state.txt` | `project_assets` | `asset_type='character_state'` |
| `global_summary.txt` | `project_assets` | `asset_type='global_summary'` |
| `chapters/chapter_{N}.txt` | `chapters` | `chapter_num`, `draft` / `finalized_text` |
| `outline_{N}.txt` | `chapters` | `outline` |
| `memory/*.json` | `project_assets` | `asset_type` 对应各类 memory |
| `vectorstore/` | Chroma 本地存储 | 按 `project_id` 隔离目录 |
| `episode_*.json` | `drama_episodes` | `outline_json` + `script_json` |

---

## 历史变更记录

| 日期 | 变更 | 说明 |
|------|------|------|
| 2026-05-05 | 初始化 | 创建 users / projects / chapters / project_assets |
| 2026-05-05 | 添加 tasks | 异步任务记录 |
| 2026-05-05 | 添加 drama_episodes | 短剧集（扁平化设计，直接关联 projects） |
| 2026-05-09 | 添加 chat | chat_sessions / chat_messages |
| 2026-05-10 | users 表新增 LLM 配置字段 | `llm_api_key_encrypted` / `llm_base_url` / `llm_model` / `llm_config_updated_at` |
| 2026-08-06 | V3 P3-B 闭环 | `arc_summaries.book_summary` 由单章最后一章合成并闭环注入（伏笔提醒命中时）；`foreshadowing.known_by` 由写前【信息约束】消费（每章最近 5 条 + 提醒命中） |

### 扁平化设计决策（D005）

MVP 阶段采用扁平化短剧数据模型：
- 不创建 `drama_projects` 表，短剧集直接关联 `projects`
- 不创建 `drama_scripts` 表，脚本数据存入 `drama_episodes.script_json`
- 不创建 `api_configs` 表，LLM 配置通过环境变量管理

如需在 Phase 2 扩展为多项目协作或支持多 LLM 配置切换，可再引入中间表。
