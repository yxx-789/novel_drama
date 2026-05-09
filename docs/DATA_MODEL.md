# 数据模型文档

## 设计原则

1. **MVP 优先简化**：不过度拆表，半结构化内容统一放入 `project_assets`
2. **旧项目兼容**：数据格式需能容纳现有 AI_NovelGenerator 和 novel_to_drama 的输出结构
3. **可扩展**：预留版本字段，后续结构调整不影响现有数据

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
| created_at | TIMESTAMP | DEFAULT now() | 创建时间 |

**索引**：email（登录查询）

---

### projects

小说项目，一个项目对应一部长篇小说。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 项目唯一标识 |
| name | VARCHAR(255) | NOT NULL | 项目名称 |
| topic | TEXT | | 小说主题 |
| genre | VARCHAR(100) | | 小说类型 |
| num_chapters | INTEGER | DEFAULT 0 | 计划章节数 |
| word_number | INTEGER | DEFAULT 0 | 计划每章字数 |
| owner_id | UUID | FK → users.id | 项目创建者 |
| status | VARCHAR(20) | DEFAULT 'draft' | 状态：draft / generating / completed |
| created_at | TIMESTAMP | DEFAULT now() | |
| updated_at | TIMESTAMP | DEFAULT now() | |

**索引**：owner_id（列表查询）

**说明**：
- MVP 阶段单人使用，owner_id 即为唯一用户
- Phase 2 引入 project_members 后才需要联表查询权限

---

### project_members

项目成员关系（Phase 2 启用，Phase 1 预留表结构）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, NOT NULL | |
| user_id | UUID | FK → users.id, NOT NULL | |
| role | VARCHAR(20) | DEFAULT 'editor' | admin / editor / viewer |
| joined_at | TIMESTAMP | DEFAULT now() | |

**唯一约束**：(project_id, user_id)

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
| status | VARCHAR(20) | DEFAULT 'pending' | pending / draft / finalized |
| version | INTEGER | DEFAULT 1 | 乐观锁版本号 |
| updated_at | TIMESTAMP | DEFAULT now() | |

**唯一约束**：(project_id, chapter_num)
**索引**：project_id（按项目查询章节）

**说明**：
- `outline`：Step2 生成目录时写入
- `draft`：Step3 生成章节草稿时写入
- `finalized_text`：Step4 定稿或用户手动编辑后写入
- `status` 流转：pending → draft（生成草稿）→ finalized（定稿完成）

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
| updated_at | TIMESTAMP | DEFAULT now() | |

**唯一约束**：(project_id, asset_type)
**索引**：project_id

**asset_type 枚举**：

| 类型 | 内容说明 | 来源 |
|------|---------|------|
| architecture | 小说架构（世界观、角色、情节蓝图） | AI_NovelGenerator Step1 |
| directory | 章节目录（JSON 格式，含标题/目的/悬念） | AI_NovelGenerator Step2 |
| character_state | 角色状态汇总 | AI_NovelGenerator Step4 |
| global_summary | 全局摘要（截至最新章节） | AI_NovelGenerator Step4 |
| world_rule | 世界规则 | AI_NovelGenerator memory |
| timeline | 时间线事件 | AI_NovelGenerator memory |
| adaptation_plan | 短剧改编计划 | novel_to_drama 大纲 |

**说明**：
- 使用 `content_json` 存储结构化数据（PostgreSQL JSONB 支持查询和索引）
- 使用 `content_text` 存储纯文本内容（如 architecture 的文本版）
- 避免为每种资产单独建表，减少 MVP 复杂度

---

### tasks

异步生成任务记录。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 任务唯一标识 |
| project_id | UUID | FK → projects.id, NOT NULL | |
| task_type | VARCHAR(50) | NOT NULL | 任务类型 |
| status | VARCHAR(20) | DEFAULT 'pending' | pending / running / success / failed / cancelled |
| progress | INTEGER | DEFAULT 0 | 进度百分比 0-100 |
| params | JSONB | | 任务参数（如章节号等） |
| result | JSONB | | 任务结果（如生成内容摘要） |
| error_msg | TEXT | | 失败原因 |
| created_at | TIMESTAMP | DEFAULT now() | |
| updated_at | TIMESTAMP | DEFAULT now() | |

**索引**：project_id（按项目查询任务列表）

**task_type 枚举**：

| 类型 | 说明 |
|------|------|
| architecture | 生成小说架构 |
| directory | 生成章节目录 |
| chapter | 生成单章草稿 |
| drama_plan | 生成短剧改编计划 |
| drama_script | 生成分集脚本 |
| export | 导出任务 |

**说明**：
- `params` 存储创建任务时传入的参数
- `result` 存储生成结果摘要（如生成的章节 ID、Token 消耗等）
- 详细生成内容写入 chapters / project_assets，不在 task 中冗余存储
- 当前为任务桩（mock 状态流转），后续接入真实 worker

---

### drama_projects

短剧改编项目。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| source_project_id | UUID | FK → projects.id, NOT NULL | 来源小说项目 |
| name | VARCHAR(255) | NOT NULL | 短剧项目名称 |
| episode_duration | INTEGER | DEFAULT 90 | 每集时长（秒） |
| max_scenes | INTEGER | DEFAULT 8 | 每集最大场景数 |
| status | VARCHAR(20) | DEFAULT 'draft' | draft / generating / completed |
| created_at | TIMESTAMP | DEFAULT now() | |

**索引**：source_project_id

---

### drama_episodes

短剧集。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| drama_project_id | UUID | FK → drama_projects.id, NOT NULL | |
| episode_num | INTEGER | NOT NULL | 集数 |
| outline_json | JSONB | | 本集大纲（hook / beats / cliffhanger） |
| status | VARCHAR(20) | DEFAULT 'pending' | pending / generated |
| created_at | TIMESTAMP | DEFAULT now() | |

**唯一约束**：(drama_project_id, episode_num)

---

### drama_scripts

分镜头脚本详情。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| episode_id | UUID | FK → drama_episodes.id, NOT NULL | |
| scene_num | INTEGER | NOT NULL | 场景号 |
| shot_num | INTEGER | NOT NULL | 镜头号 |
| shot_type | VARCHAR(50) | | 镜头类型：close_up / medium / wide 等 |
| duration | INTEGER | | 时长（秒） |
| location | VARCHAR(255) | | 场景地点 |
| visual | TEXT | | 画面描述 |
| action | TEXT | | 动作描述 |
| dialogue | TEXT | | 台词 |
| speaker | VARCHAR(100) | | 说话人 |
| camera_movement | VARCHAR(100) | | 运镜方式 |
| audio | VARCHAR(100) | | BGM / 音效 |
| created_at | TIMESTAMP | DEFAULT now() | |

**唯一约束**：(episode_id, scene_num, shot_num)
**索引**：episode_id

---

### chat_sessions

AI 问答会话。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| project_id | UUID | FK → projects.id, nullable | 关联项目（可为空，表示通用问答） |
| user_id | UUID | FK → users.id, NOT NULL | 会话所有者 |
| title | VARCHAR(255) | nullable | 会话标题（自动生成） |
| created_at | TIMESTAMP | DEFAULT now() | |
| updated_at | TIMESTAMP | DEFAULT now() | |

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
| created_at | TIMESTAMP | DEFAULT now() | |
| updated_at | TIMESTAMP | DEFAULT now() | |

**索引**：session_id

---

### api_configs

用户 LLM API 配置。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| user_id | UUID | FK → users.id, NOT NULL | |
| name | VARCHAR(100) | NOT NULL | 配置名称（如"DeepSeek 生产"） |
| provider | VARCHAR(50) | NOT NULL | openai / deepseek / qianfan 等 |
| api_key | VARCHAR(500) | NOT NULL | 加密存储 |
| base_url | VARCHAR(500) | | API 基础地址 |
| model_name | VARCHAR(100) | NOT NULL | 模型名称 |
| temperature | FLOAT | DEFAULT 0.7 | |
| max_tokens | INTEGER | DEFAULT 8192 | |
| is_default | BOOLEAN | DEFAULT false | 是否为默认配置 |
| created_at | TIMESTAMP | DEFAULT now() | |

**说明**：
- MVP 阶段每个用户管理自己的配置
- Phase 2 可扩展为团队共享配置
- `api_key` 在应用层加密存储（如使用 Fernet），不在日志中输出

---

## E-R 关系图

```
users ||--o{ projects : owns
users ||--o{ api_configs : has
users ||--o{ generation_tasks : creates

projects ||--o{ chapters : contains
projects ||--o{ project_assets : has
projects ||--o{ generation_tasks : generates
projects ||--o{ drama_projects : adapts_to
projects ||--o{ project_members : has

users ||--o{ project_members : belongs_to

drama_projects ||--o{ drama_episodes : contains
drama_episodes ||--o{ drama_scripts : has
```

---

## Phase 1 数据模型范围

### 必须创建的表

按依赖顺序：

1. `users` —— 认证基础
2. `api_configs` —— LLM 调用依赖
3. `projects` —— 业务核心
4. `chapters` —— 小说内容
5. `project_assets` —— 半结构化资产
6. `generation_tasks` —— 异步任务
7. `drama_projects` —— 短剧项目
8. `drama_episodes` —— 短剧集
9. `drama_scripts` —— 分镜头脚本

### Phase 1 预留但不填充数据的表

- `project_members` —— 表结构创建，数据由 Phase 2 填充

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
| `config.json` | `api_configs` | 多模型配置按行存储 |
| `episode_*.json` | `drama_episodes` + `drama_scripts` | 拆分存储 |
