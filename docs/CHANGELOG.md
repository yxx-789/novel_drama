# 变更日志

## [未发布]

### 修复

- **批量章节生成失败**：`generate_chapter_draft` 和 `update_character_state` 中 LLM API key 检查逻辑与 `generate_architecture` 不一致，仅检查全局 `settings.LLM_API_KEY` 而忽略用户自定义的 `llm_config.api_key`，导致使用个人 API key 时批量生成全部失败
  - `backend/app/services/generation_service.py`：统一两处检查逻辑为 `if not settings.LLM_API_KEY and not (llm_config and llm_config.get("api_key"))`
- **世界状态始终为空**：`extract_world_state_delta` 和 `build_state_summary` 存在同样的 API key 检查缺失，导致个人 API key 模式下世界状态提取被静默跳过
  - `backend/app/services/generation_service.py`：修复两处检查逻辑
- **批量短剧脚本生成失败**：`drama_service.py` 中 `generate_drama_script` 被重复定义（后一个定义无 `llm_config` 参数），覆盖了带参数的版本，`task_service.py` 传入 `llm_config` 时触发 `unexpected keyword argument`
  - `backend/app/services/drama_service.py`：删除第二个重复定义，保留带 `llm_config` 的版本

### 新增

- **Celery 持久化任务队列集成**
  - 新增 `backend/app/core/celery_app.py` —— Celery 应用配置（Redis broker + backend）
  - 新增 `backend/app/worker/tasks.py` —— 7 个 Celery 任务包装器（architecture / directory / chapter / batch_chapters / drama_plan / drama_episode / drama_batch），通过 `asyncio.run()` 复用现有异步业务代码
  - 新增 `docker-compose.yml` `worker` 服务 —— 独立 Celery worker 容器，`-c 1` 单并发避免 LLM 限流
  - 新增 `POST /api/tasks/{task_id}/cancel` —— 任务取消 API，调用 `celery_app.control.revoke(terminate=True)`
  - 重写 `backend/app/routers/generate.py` —— 所有生成接口从 `asyncio.create_task()` 切换为 `celery_task.delay()`
  - 更新 `backend/app/main.py` —— lifespan 启动时执行 `recover_zombie_tasks()`：扫描运行中超 30 分钟任务并标记为 failed，防止 worker 重启导致任务悬挂
  - `backend/requirements.txt` 新增 `celery==5.4.0`
  - 决策更新：`memory-bank/decisions.md` D004 从 "RQ/Dramatiq" 修正为 **Celery + Redis**

- **生产部署配置**
  - 新增 `backend/Dockerfile` —— 多阶段构建生产镜像（Python 3.12 slim + 依赖分层缓存）
  - 新增 `railway.toml` —— Railway 平台部署配置（自动迁移 + 健康检查 + 失败重启策略）
  - 更新 `backend/app/main.py` —— CORS 支持 `CORS_ORIGINS` 环境变量配置，便于生产环境限制域名
  - 更新 `backend/.env.example` —— 补充 `FERNET_SECRET`、`LLM_*`、`CORS_ORIGINS` 等生产环境变量
  - 更新 `frontend/.env.example` —— 补充生产环境 API 地址说明
  - 新增 `docs/DEPLOYMENT.md` —— Railway + Vercel 部署完整指南

- 短剧脚本导出功能：支持 JSON / Markdown / CSV 三种格式下载
  - 后端：`backend/app/services/drama/exporter.py` 纯内存格式化服务（复用旧项目核心逻辑）
  - 后端：`GET /api/drama/episodes/{ep_id}/export?format=json|md|csv` 同步下载接口
  - 前端：`frontend/src/api/drama.ts` 新增 `exportEpisodeScript()`
  - 前端：`ProjectDetail.tsx` 短剧 Tab 新增导出按钮（JSON / MD / CSV）

- 导出选择与批量导出：章节和剧集均支持复选框多选 + 批量导出
  - 后端：`POST /api/chapters/export/batch` 批量导出选中章节（md/json）
  - 后端：`POST /api/drama/episodes/export/batch` 批量导出选中剧集脚本（md/json）
  - 前端：章节 Tab 新增全选/导出选中按钮
  - 前端：短剧 Tab 新增全选/导出选中（MD/JSON）按钮

- 脚本生成章节选择 + 续集记忆机制
  - 后端：`POST /projects/{id}/generate/drama-episode/{num}` 支持 `chapter_nums` 参数，指定基于哪些章节生成
  - 后端：`drama_service.py` 新增 `_build_context_summary()`，提取前 3 集关键道具和结尾台词注入 prompt
  - 后端：`task_service.py` `run_drama_episode_task()` / `run_drama_batch_task()` 自动查询前集脚本作为上下文
  - 前端：点击"生成脚本"时弹出章节选择器模态框，支持全选/按默认选择/自定义勾选
  - 前端：章节选择器采用 glass-panel 风格，与现有 UI 一致

### 文档

- 新增 `AGENTS.md` —— 项目协作规范与开发约束
- 新增 `docs/PRD.md` —— 项目需求文档（修订版）
- 新增 `memory-bank/progress.md` —— 项目进度追踪
- 创建 `docs/`、`memory-bank/` 目录结构

### 决策

- 确定技术栈：FastAPI + React + PostgreSQL + Redis + 任务队列
- 确定异步任务队列候选：RQ / Dramatiq / Celery（MVP 优先 RQ 或 Dramatiq）
- 确定部署方案：前端 Vercel + 后端 Railway/Render
- 确定 MVP 范围：单人闭环，暂不实现实时协作

### 新增文档

- 新增 `docs/ARCHITECTURE.md` —— 系统架构、模块边界、异步任务流转、旧代码迁移方式
- 新增 `docs/ROADMAP.md` —— Phase 1-3 路线图，明确 MVP 做什么/不做什么
- 新增 `docs/DATA_MODEL.md` —— 9 张核心表 + project_assets 半结构化资产设计
- 新增 `memory-bank/decisions.md` —— 11 条关键决策记录（含技术选型、数据模型、MVP 范围）

### Phase 1 脚手架搭建

- 新增 `backend/` 目录结构（core/infra/models/schemas/routers/services）
- 新增 `frontend/` 目录结构（api/components/pages/hooks/store/types）
- 后端基础框架：FastAPI + SQLAlchemy 2.0（asyncpg）+ Alembic
- 前端基础框架：React + TypeScript + Vite + Tailwind CSS + Zustand
- 数据库模型：users / projects / chapters / project_assets（4 张基础表）
- Alembic 初始 migration 生成并应用到 PostgreSQL
- docker-compose.yml：PG + Redis + Backend 服务编排
- 后端可启动，/health 返回 OK
- 前端可编译，包含 Login / Dashboard 壳子页面

### 认证 API 最小业务闭环

- 后端认证模块：注册、登录、JWT Token、当前用户信息
- 新增 `backend/app/schemas/user.py` + `token.py` —— Pydantic 请求/响应模型
- 新增 `backend/app/services/auth_service.py` —— 注册、认证、查询用户业务逻辑
- 新增 `backend/app/routers/dependency.py` —— get_current_user JWT 依赖
- 重写 `backend/app/routers/auth.py` —— 三个认证接口真实实现
- 后端挂载 `/api/auth` 路由前缀
- 前端 `frontend/src/api/auth.ts` —— Axios 封装认证 API
- 前端 `frontend/src/pages/Login.tsx` —— 接入真实登录/注册 API，支持登录/注册切换
- 前端 `frontend/src/pages/Dashboard.tsx` —— 展示当前用户信息，退出登录
- 数据流贯通：前端表单 → 后端 API → 数据库读写 → JWT 鉴权 → 前端状态
- 全部 5 项验收标准通过（curl 注册/登录/me + 前端联调）

### 项目 API（CRUD）最小业务闭环

- 后端项目 schemas：`backend/app/schemas/project.py` —— ProjectCreate, ProjectUpdate, ProjectOut
- 后端项目 service：`backend/app/services/project_service.py` —— create/get/list/update/delete，owner_id 隔离
- 后端项目 router：`backend/app/routers/projects.py` —— 5 个 REST 接口，全部依赖 get_current_user
- 后端挂载 `/api/projects` 路由，严格按 owner_id 鉴权（非 owner 返回 404）
- 前端 `frontend/src/api/project.ts` —— Axios 封装项目 CRUD API
- 前端 `frontend/src/pages/ProjectList.tsx` —— 项目卡片列表，支持删除
- 前端 `frontend/src/pages/ProjectCreate.tsx` —— 创建项目表单
- 前端 `frontend/src/pages/ProjectDetail.tsx` —— 项目详情 + 基础编辑
- 前端路由更新：`/projects`, `/projects/create`, `/projects/:id`
- 全部 9 项验收标准通过（curl 创建/列表/详情/更新/删除 + 无 Token 401 + 所有权隔离）

### 章节 API（CRUD）最小业务闭环

- 后端章节 schemas：`backend/app/schemas/chapter.py` —— ChapterCreate, ChapterUpdate, ChapterOut
- 后端章节 service：`backend/app/services/chapter_service.py` —— create/get/list/update/delete，project_id 关联 + owner_id 隔离
- 后端章节 router：`backend/app/routers/chapters.py` —— 5 个 REST 接口（嵌套 + 独立路由混合）
- 后端修复 asyncpg UUID 类型兼容（`str()` 转换后再构造 `uuid.UUID`）
- 后端挂载 `/api/projects/{id}/chapters` 和 `/api/chapters/{id}` 路由
- 前端 `frontend/src/api/chapter.ts` —— Axios 封装章节 CRUD API
- 前端 `frontend/src/pages/ProjectDetail.tsx` —— 项目详情页集成章节列表、新建、编辑、删除
- 前端类型修复：`CreateChapterRequest` / `UpdateChapterRequest` 字段允许 `string | null`
- 全部 5 项验收标准通过（curl 创建/列表/详情/更新/删除 + 所有权隔离）

### 任务系统 + 异步任务桩 + 资产读写 最小业务闭环

- 新增 `tasks` 表： Alembic migration `5e3a33577bdd_add_tasks_table.py` 生成并成功应用
- 后端 Task 模型：`backend/app/models/project.py` —— Task 模型（project_id/task_type/status/progress/params/result/error_msg）
- 后端 Task schemas：`backend/app/schemas/task.py` —— TaskCreate, TaskOut
- 后端 Task service：`backend/app/services/task_service.py` —— create/get/list/update_status
- 后端 Task router：`backend/app/routers/tasks.py` —— POST/GET /projects/{id}/tasks, GET /tasks/{id}
- 后端 Generate router（桩）：`backend/app/routers/generate.py` —— architecture/directory/chapter 生成任务创建
- 后端 Assets router：`backend/app/routers/assets.py` —— GET/PUT /projects/{id}/assets/{type}
- 后端 `main.py` —— 挂载 tasks/generate/assets 路由
- 前端 `frontend/src/api/task.ts` —— createTask/listTasks/getTask
- 前端 `frontend/src/api/asset.ts` —— getAsset/upsertAsset
- 前端编译通过
- docs/API_SPEC.md —— 登记任务/生成/资产接口
- docs/DATA_MODEL.md —— 更新 tasks 表说明（表名统一为 tasks，字段 params/result）

### 接入真实 LLM Architecture 生成

- 复用 `AI_NovelGenerator/prompts/architecture_prompts.py` → `backend/app/generator/prompts.py`
- 新增 `backend/app/generator/llm_adapter.py` —— 异步 OpenAI-Compatible Adapter（httpx）
- 新增 `backend/app/services/generation_service.py` —— 改造后的 5 步 architecture pipeline（异步 + 返回文本）
- 更新 `backend/app/services/task_service.py` —— `run_architecture_task()` 后台编排：task 状态流转 + 调用 generation_service + 写入 project_assets
- 更新 `backend/app/routers/generate.py` —— architecture 创建任务后触发 `asyncio.create_task(run_architecture_task())`
- 更新 `backend/app/core/config.py` —— 新增 LLM 默认配置项（LLM_INTERFACE_FORMAT / BASE_URL / MODEL / API_KEY / TEMPERATURE / MAX_TOKENS / TIMEOUT）
- 后端 import 验证通过，前端编译通过
- docs/API_SPEC.md —— architecture 标记为"真实 LLM"

### 接入真实 LLM Directory 生成

- 复用 `AI_NovelGenerator/prompts/blueprint_prompts.py` → `backend/app/generator/prompts.py`
- 复用 `AI_NovelGenerator/chapter_directory_parser.py` → `backend/app/services/generation_service.py`（`parse_chapter_blueprint`）
- 新增 `generation_service.generate_directory()` —— 读取 architecture asset → LLM 生成目录 → 解析为结构化数据
- 更新 `task_service.py` —— 新增 `run_directory_task()`：读取 architecture → 生成 directory → 写入 project_assets → 初始化 chapters 表
- 更新 `generate.py` —— directory 接口创建任务后触发 `asyncio.create_task(run_directory_task())`
- 后端 import 验证通过

### 前端项目工作台 Tab 页面

- 重构 `frontend/src/pages/ProjectDetail.tsx` —— Tab 布局：概览 / 架构 / 目录 / 章节
- 概览 Tab：项目信息展示 + 编辑（保留原有功能）
- 架构 Tab：architecture asset 文本编辑 + 保存 + AI 生成任务触发
- 目录 Tab：directory asset 文本编辑 + 保存 + AI 生成任务触发
- 章节 Tab：章节列表/新建/编辑/删除（完整迁移原有功能）
- Tab 切换时按需加载对应 asset 数据
- 前端编译通过

### 短剧改编 API（异步任务桩）

- 新增 `drama_episodes` 表：Alembic migration `8a79b9d90021_add_drama_episodes_table.py` 生成并成功应用
- 后端 DramaEpisode 模型：`backend/app/models/project.py` —— project_id/episode_num/title/source_chapters/outline_json/script_json/status
- 后端 DramaEpisode schema：`backend/app/schemas/drama.py` —— DramaEpisodeOut
- 后端 Drama router：`backend/app/routers/drama.py` —— GET /projects/{id}/drama-episodes
- 后端 Generate router：`backend/app/routers/generate.py` —— 新增 `drama-plan` / `drama-episode/{num}` 触发端点
- 后端 task_service：`backend/app/services/task_service.py` —— 新增 `run_drama_plan_task()`（按每 3 章分组生成剧集计划）和 `run_drama_episode_task()`（生成占位脚本数据）
- 后端 `main.py` —— 挂载 drama 路由
- 前端 `frontend/src/api/drama.ts` —— listDramaEpisodes
- 前端 `frontend/src/pages/ProjectDetail.tsx` —— 新增"短剧改编"Tab：AI 生成改编计划 + 单集脚本生成 + 任务轮询自动刷新
- 前端编译通过
- docs/API_SPEC.md / DATA_MODEL.md —— 更新 drama 相关接口和模型说明

### 接入真实 LLM Chapter 生成

- 复用 `AI_NovelGenerator/prompts/chapter_prompts.py` → `backend/app/generator/prompts.py`（MVP 简化版，去除 MemoryManager / RAG / Planning Layer 依赖）
- 新增 `backend/app/services/generation_service.py` —— `generate_chapter_draft()`：读取 architecture + directory + previous chapter draft → LLM 生成单章正文
- 更新 `backend/app/services/task_service.py` —— `run_chapter_task()` 后台编排：task 状态流转 → 读取前置资产 → 调用 generation_service → 写入 `chapters.draft`
- 更新 `backend/app/routers/generate.py` —— chapter 接口创建任务后触发 `asyncio.create_task(run_chapter_task())`
- 后端 import 验证通过
- 前端 `frontend/src/pages/ProjectDetail.tsx` —— 章节卡片增加 "AI 生成" 按钮，支持单章独立触发
- 前端任务状态轮询机制：`pollTask` 辅助函数，每 3 秒查询 `getTask`，任务完成/失败后自动停止并刷新数据
- 架构/目录生成也接入轮询，替代 `alert`，任务完成后自动刷新对应 Tab 数据
- 前端编译通过

### 角色状态追踪（随章节生成自动更新）

- 新增 `backend/app/generator/prompts.py` —— `update_character_state_prompt`：复用 AI_NovelGenerator `memory_prompts.py` 核心 prompt
- 修改 `backend/app/generator/prompts.py` —— `next_chapter_draft_prompt` 注入 `{character_state}` 占位符
- 新增 `backend/app/services/generation_service.py` —— `update_character_state()`：读取旧状态 + 新章节正文 → LLM 更新角色状态文档
- 修改 `backend/app/services/generation_service.py` —— `generate_chapter_draft()` 新增 `character_state_text` 参数
- 修改 `backend/app/services/task_service.py` —— `run_chapter_task()` / `run_batch_chapters_task()`：生成前读取 `characters` asset，生成后调用 `update_character_state()` 写入最新状态
- 前端架构 Tab 同步加载并展示 `characters` asset 内容（只读）
- 后端 import / py_compile / 服务启动验证通过
- 实测：角色状态从 3657 字符更新为 4554 字符，物品/能力/状态均按剧情正确演化

### 短剧改编 API（复用 novel_to_drama 真实 LLM）

- 新建 `backend/app/services/drama_service.py` —— 复用 `novel_to_drama` 核心 prompt 逻辑：
  - `generate_drama_outline()`：章节文本 + 角色设定 → LLM → JSON 大纲（hook / story_beats / cliffhanger / key_items）
  - `generate_drama_script()`：大纲 + 原始小说 → LLM → JSON 分镜头剧本（scenes / shots / dialogue / camera_movement / audio）
- 替换 `backend/app/services/task_service.py` —— `run_drama_plan_task()` stub → 真实 LLM：按每 3 章一集分组，逐集生成 outline_json 并保存
- 替换 `backend/app/services/task_service.py` —— `run_drama_episode_task()` stub → 真实 LLM：读取 episode outline + 对应章节正文 → 生成分镜头 script_json
- 增强 `drama_service._parse_llm_json()`：去掉 "json" 前缀、修复截断括号（补全缺失的 `}` 和 `]`）
- drama script 生成使用 12000 max_tokens（避免 4096 token 截断）
- 后端 import / py_compile / 服务启动验证通过
- 实测：3 章小说生成 10 场景 / 29 镜头的完整分镜脚本，关键道具和逻辑链条全部保留

### 短剧改编 Tab 重构（模块化卡片 + 可读化脚本 + 映射管理）

- 后端新增 3 个 PUT 接口：
  - `PUT /drama/episodes/{id}/outline` —— 更新 outline_json
  - `PUT /drama/episodes/{id}/script` —— 更新 script_json
  - `PUT /drama/episodes/{id}/source-chapters` —— 更新 source_chapters
- 前端新增 `ScriptViewer` 组件：将 script_json 渲染为导演分镜格式（场景/镜头/台词/音效）
- 前端新增 `EpisodeCard` 组件：模块化剧集卡片，包含：
  - 头部：集号、可编辑标题、状态 badge（彩色进度点）
  - 来源章节区：标签化展示 + 移除按钮 + 下拉添加未分配章节
  - 大纲区：折叠/展开，渲染 hook / story_beats / cliffhanger / key_items
  - 脚本区：ScriptViewer 格式化展示
  - 前集续接条：自动提取上一集结尾台词作为上下文
  - 操作栏：生成/重新生成、展开/收起、导出（MD/JSON/CSV）
- 前端 `ProjectDetail.tsx` 短剧 Tab 重构：纵向列表 → EpisodeCard 列表
- 前端 `api/drama.ts` 新增：`updateEpisodeOutline` / `updateEpisodeScript` / `updateSourceChapters`
- 大纲内联编辑：点击"编辑"进入 JSON textarea 编辑模式，保存后即时更新
- TypeScript 编译通过
- docs/API_SPEC.md / CHANGELOG.md / progress.md 同步更新

### 结构化世界状态记忆（长程一致性基础设施）

- **Genre Templates**
  - 新增 `backend/app/generator/world_state_templates.py`
  - 定义 `GENERIC_TEMPLATE`（通用）、`XIANXIA_TEMPLATE`（修仙/玄幻/武侠）、`URBAN_TEMPLATE`（都市/现代/商战/系统）三套追踪维度 schema
  - `get_template(genre)` 按 genre 字符串自动匹配最合适的模板

- **Prompt 层**
  - `backend/app/generator/prompts.py` 新增 `extract_world_state_delta_prompt`：要求 LLM 从章节正文中提取结构化 JSON 变更 delta（characters / events / world 三类）
  - 新增 `build_state_summary_prompt`：要求 LLM 从当前世界状态中筛选 5-10 条与下一章最相关的状态点

- **Generation Service 扩展**
  - `backend/app/services/generation_service.py`：
    - `_parse_llm_json()`：鲁棒 JSON 提取（去 markdown 代码块、补全截断括号）
    - `extract_world_state_delta()`：异步 LLM 调用，按 genre 模板提取 delta
    - `merge_world_state()`：深合并 delta 到旧状态 + 自动记录变更历史（chapter / category / key / field / old / new）
    - `build_state_summary()`：异步 LLM 调用，生成注入下一章 prompt 的状态摘要
    - `generate_chapter_draft()` 新增 `world_state_summary: str = ""` 参数，摘要追加在 character_state 后注入 prompt

- **Task Service 集成**
  - `run_chapter_task()` / `run_batch_chapters_task()`：
    - 生成前：读取 `world_state` asset → 调用 `build_state_summary()` → 追加到 character_state
    - 生成后：调用 `extract_world_state_delta()` → 若无 `no_changes` 则 `merge_world_state()` → 保存回 asset
  - 向后兼容：无 world_state asset 时自动初始化空结构，不影响旧项目

- **前端「角色与世界」Tab**
  - 新增 `frontend/src/pages/ProjectDetail/WorldStateTab.tsx`
  - 读取 `world_state` asset（优先 `content_json`，fallback `content_text` JSON 解析）
  - 三栏卡片展示：角色状态 🧑 / 事件追踪 📌 / 世界设定 🌍
  - 变更历史时间线：按章节倒序，每项显示 category icon + key · field + old → new（删除线/绿色高亮）
  - 空状态引导：未生成章节时显示友好提示"生成章节后会自动构建角色与世界状态追踪"
  - `frontend/src/pages/ProjectDetail/index.tsx`：TabKey / tabs 数组 / 条件渲染 集成

- 后端 import 验证通过，前端构建零警告

### 后端生成质量与稳定性优化

- **修复 world_state_summary 未注入 prompt**
  - `backend/app/generator/prompts.py`：`first_chapter_draft_prompt` / `next_chapter_draft_prompt` 新增 `{world_state_summary}` 独立占位符
  - `backend/app/services/generation_service.py`：`generate_chapter_draft()` 将 `world_state_summary` 作为独立参数传入 prompt（不再拼接到 `character_state_text`），避免重复且让 LLM 明确识别世界状态约束
  - `backend/app/services/task_service.py`：`run_chapter_task()` / `run_batch_chapters_task()` 同步调整，独立传递 `world_state_summary`

- **Prompt 写作要求强化**
  - 两版章节 prompt 新增明确约束："必须严格遵循【世界状态摘要】中的所有设定，禁止出现与摘要矛盾的情节（如已死亡角色出场、已损坏物品完好、境界/能力倒退等）"

- **LLM 输出清洗精确化**
  - `backend/app/services/generation_service.py`：`_invoke_with_retry()` 从全局 `replace("```", "")` 改为正则精确去除首尾 markdown 代码块标记（`^```[\w]*\n?` 和 `\n?```\s*$`），避免误删正文中的代码片段或类似标记

- **merge_world_state 无副作用**
  - 新增 `copy.deepcopy(delta)`，防止 `fields.pop("changed_fields")` 修改传入的原始 delta dict

- **build_state_summary Token 精简**
  - `slim_state` 除 history 截断为最近 3 章外，`characters` / `events` / `world` 每类限制最多 10 个条目，优先保留最近 3 章内有变更的实体，防止长程状态膨胀导致 prompt token 超限

- **批量生成错误隔离**
  - `backend/app/services/task_service.py`：`run_batch_chapters_task()` 循环内包裹单章 try/except
  - 单章失败时记录到 `failed_chapters` 列表（含章节号和错误信息），继续生成后续章节，不中断整个批量任务
  - 任务最终结果报告成功/失败明细

- **新增单元测试**
  - 新增 `backend/app/tests/test_world_state.py`，覆盖模板选择、JSON 解析鲁棒性、状态合并与变更历史，21 用例全部通过

- 后端 import 验证通过，前端构建零警告

### Bug 修复

- **短剧改编状态同步修复**
  - `backend/app/services/task_service.py`：修正 `run_drama_plan_task()` 设置 `episode.status = "outlined"`（原为错误值）
  - `backend/app/services/task_service.py`：修正 `run_drama_episode_task()` / `run_drama_batch_task()` 设置 `episode.status = "script_ready"`（原为 `"generated"`，前端不识别导致状态显示异常）
  - 修复后："AI 生成改编计划" 与 "AI 批量生成全部脚本" 两阶段状态区分正确显示

- **章节选择器默认范围解析修复**
  - `frontend/src/pages/ProjectDetail.tsx`：新增 `parseSourceChapters()` 函数
  - 支持解析 `"第1-3章"` / `"第1章"` / `"1,2,3"` 三种格式
  - 修复前：默认范围 `split(',').map(parseInt)` 对中文格式返回 `NaN`，导致默认选择为空

### 视觉系统修缮 + 浅色系背景

- **全局主题：暖色浅色背景**
  - `frontend/src/index.css`：body 背景从冷灰 slate 渐变改为暖色 cream 渐变（`#faf8f5` → `#f0ebe4` → `#e8e2d9`）
  - 视觉感受更柔和，适合长时间创作阅读

- **玻璃面板（glass-panel）精细化**
  - 圆角从 `2rem`（32px）降至 `1rem`（16px），更紧凑现代
  - 阴影从 `0 4px 20px rgba(0,0,0,0.03)` 调整为 `0 2px 12px rgba(0,0,0,0.04)`，更轻盈
  - 背景透明度从 `0.7` 降至 `0.65`，增强背景暖色透叠感

- **字体层次规范化（中文适配）**
  - `frontend/src/components/EpisodeCard.tsx`：全部 `text-[10px]`（约 10px，中文极难阅读）替换为 `text-xs`（12px）
  - `frontend/src/components/ScriptViewer.tsx`：同上
  - `frontend/src/pages/ProjectDetail.tsx`：移除 `tracking-widest` / `tracking-wider`，中文不宜过度字间距
  - `frontend/src/index.css`：`.btn-pill` 移除 `tracking-widest`

- **状态色板统一**
  - 全站状态 badge 统一为 Tailwind slate / indigo / amber / emerald 四色体系
  - 消除 `gray/blue/yellow/green` 与 `slate/indigo/amber/emerald` 混用导致的色差

### 用户动线引导（方案 A：嵌入式上下文引导）

- **工作流进度条**
  - `frontend/src/pages/ProjectDetail.tsx`：Tab 栏上方新增四步进度指示器
  - 步骤：架构 → 目录 → 章节 → 短剧改编
  - 已完成步骤显示绿色对勾，未完成显示序号
  - 点击任意步骤直接跳转对应 Tab，消除"不知道下一步做什么"的困惑

- **短剧 Tab 空状态引导卡片**
  - 当尚无短剧改编计划时，不再显示空白，而是展示结构化引导卡片
  - 包含：图标 + 说明文字 + 两步流程图解（①生成改编计划 → ②生成各集脚本）+ CTA 按钮

- **禁用按钮持续提示**
  - "AI 批量生成全部脚本"按钮在未生成改编计划时禁用
  - 禁用状态下，按钮下方常驻显示 `"请先生成改编计划"` 提示文本
  - 消除"按钮为什么点不了"的猜测成本

- **Tab 导航增强**
  - 当前激活 Tab 新增 `bg-indigo-50/50` 底色高亮 + `rounded-t-lg` 圆角
  - 非激活 Tab 悬停时显示 `hover:bg-slate-50/50` 反馈
  - 视觉层级更清晰，当前位置一目了然

### Bug 修复

- **修复「角色与世界」Tab 400 错误**
  - `backend/app/routers/assets.py`：`ASSET_TYPES` 白名单缺少 `"world_state"`，前端调用 `GET /projects/{id}/assets/world_state` 时返回 400 "不支持的资产类型"
  - 已添加 `"world_state"` 到白名单，后端 import 验证通过

### ProjectDetail React Query 深度替换

- 新增 `frontend/src/pages/ProjectDetail/useProjectData.ts` —— 自定义 hook 集中管理项目详情页全部数据查询与变更：
  - Queries：`['project', id]` / `['chapters', id]` / `['asset', id, type]` / `['dramaEpisodes', id]`
  - Mutations：`saveProject` / `saveAsset` / `addChapter` / `updateChapter` / `deleteChapter` / `updateEpisode` / `updateSource`
  - 所有 mutation 成功后自动 `invalidateQueries`，数据自动刷新
- 重写 `frontend/src/pages/ProjectDetail/index.tsx` —— 移除 5 个手动 `useEffect` 数据获取逻辑：
  - 项目详情、章节列表、架构/目录/人物/短剧剧集数据全部改为从 `useProjectData` 读取
  - 保留编辑态 local state（`architectureText` / `directoryText`），通过 `useEffect` 在 dirty=false 时与 query 数据同步
  - 任务完成后的数据刷新从手动 `setState` 改为 `queryClient.invalidateQueries`
- `frontend/src/pages/ProjectDetail/ArchitectureTab.tsx` / `DirectoryTab.tsx` —— props 精简：
  - 移除 `setXxxText` 和 `setDirty`，改为接收 `value` + `onChange` 回调，组件更纯粹
- `frontend/src/pages/ProjectDetail/WorldStateTab.tsx` —— 接入 React Query：
  - 移除内部 `useEffect` + `useState`，改为 `useQuery(['asset', id, 'world_state'])`
- 前端构建零警告

### AI 问答功能

- **后端：数据模型**
  - 新增 `chat_sessions` 表：id, project_id, user_id, title, created_at, updated_at
  - 新增 `chat_messages` 表：id, session_id, role, content, model_name, tokens_used, meta_json, created_at, updated_at
  - Alembic migration `d512a3fe455d_add_chat_sessions_and_messages.py` 自动生成并成功应用
  - `backend/alembic/env.py`：添加 chat 模型导入确保 autogenerate 正常工作

- **后端：API 层**
  - `backend/app/schemas/chat.py`：ChatSessionOut, ChatMessageOut, ChatSessionDetailOut, ChatMessageCreate, ChatSessionCreate
  - `backend/app/services/chat_service.py`：会话 CRUD + LLM 调用逻辑
    - `create_session` / `list_sessions` / `get_session_with_messages` / `send_message`
    - `send_message` 自动注入项目上下文（architecture + directory）作为 system prompt
    - 复用 `llm_adapter.py`，新增 `invoke_messages()` 方法支持多轮对话 messages 格式
  - `backend/app/routers/chat.py`：5 个 REST 接口（获取/创建会话、获取详情、发送消息）
  - `backend/app/main.py`：挂载 `/api/chat` 路由

- **前端：AI 问答抽屉**
  - `frontend/src/api/chat.ts`：API 封装（listProjectChatSessions, createChatSession, getChatSession, sendChatMessage）
  - `frontend/src/components/AIChatDrawer.tsx`：右侧滑出抽屉组件
    - glass-panel 风格，宽度 420px
    - 消息区：用户消息右对齐（indigo 底色），AI 消息左对齐（白色底色）
    - 空状态：图标 + 说明 + 4 个快捷问题按钮
    - 加载态：弹跳圆点动画
    - 会话列表：切换/新建会话
    - 输入区：textarea + 发送按钮，支持 Enter 发送、Shift+Enter 换行
  - `frontend/src/pages/ProjectDetail.tsx`：
    - 顶部 header 右侧新增 "AI 助手" 入口按钮
    - 集成 AIChatDrawer 组件
  - TypeScript 编译通过
