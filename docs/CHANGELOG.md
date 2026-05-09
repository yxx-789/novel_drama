# 变更日志

## [未发布]

### 新增

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
