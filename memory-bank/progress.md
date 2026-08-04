# 项目进度追踪

## 当前阶段

Phase 1: 最小业务闭环 —— 项目 API（已完成）

## 本次会话：配置与稳定性修复（2026-08-04）

- [x] 平台默认 LLM 切换为 DeepSeek（`https://api.deepseek.com` / `deepseek-chat` / `max_tokens=8192`）
- [x] 定位并修复生成卡死根因：`deepseek-v4-flash` 推理模型在 2048 预算下 `content` 空输出 → 重试循环
- [x] 修复世界状态功能连续 3 个缺陷：缺 `import json`、prompt 模板花括号未转义、`merge_world_state` 不兼容扁平 `world` 结构
- [x] 世界状态链路实测通过（extract → merge → build_state_summary），`test_world_state.py` 23 用例全部通过
- [x] `requirements.txt` 新增 `email-validator`、钉住 `bcrypt==4.0.1`（启动 + 注册 500）
- [x] 本地 docker-compose 全栈跑通（Docker Hub 不可达时经 `docker.m.daocloud.io` 镜像源拉取基础镜像）
- [x] 前后端启动、健康检查、注册/登录、DeepSeek 调用链路实测通过
- [ ] 待用户重新生成架构/目录/章节验证修复效果

## 已完成事项

### Phase 0 文档

- [x] 项目定位与整合方向确定（AI_NovelGenerator + novel_to_drama → Web 工作台）
- [x] AGENTS.md 协作规范制定并保存
- [x] docs/PRD.md 修订版完成
- [x] 项目目录结构规划（docs/、memory-bank/、backend/、frontend/）
- [x] 技术栈确定（FastAPI + React + PostgreSQL + Redis + 任务队列）
- [x] docs/ARCHITECTURE.md —— 系统架构文档
- [x] docs/ROADMAP.md —— 详细路线图
- [x] docs/DATA_MODEL.md —— 数据模型文档
- [x] memory-bank/decisions.md —— 关键决策记录
- [x] docs/CHANGELOG.md —— 变更日志更新

### Phase 1 脚手架

- [x] backend/ 目录结构与基础框架（FastAPI + SQLAlchemy 2.0 async）
- [x] 后端配置管理（Pydantic Settings）
- [x] 后端安全工具（JWT + bcrypt）
- [x] 后端数据库连接（asyncpg + SessionLocal）
- [x] 后端 Redis 连接封装
- [x] 后端数据库模型（users, projects, chapters, project_assets）
- [x] Alembic 初始 migration 生成并成功应用
- [x] docker-compose.yml（PG + Redis + Backend）
- [x] frontend/ 目录结构与基础框架（React + TypeScript + Vite）
- [x] 前端 Axios 封装 + Zustand 认证状态
- [x] 前端 Login / Dashboard 壳子页面
- [x] 前端编译通过

### 认证 API 闭环

- [x] 后端认证 schemas（UserCreate, UserLogin, UserOut, Token）
- [x] 后端认证 service（register, authenticate, get_user_by_id/username/email）
- [x] 后端 get_current_user JWT dependency
- [x] 后端 auth router（POST /register, POST /login, GET /me）
- [x] 前端 api/auth.ts（login, register, getCurrentUser）
- [x] 前端 Login 页面（真实 API，登录/注册切换，错误提示）
- [x] 前端 Dashboard 页面（用户信息展示，退出登录）
- [x] 前后端联调通过
- [x] docs/API_SPEC.md 认证接口更新

### 项目 API（CRUD）闭环

- [x] 后端项目 schemas（ProjectCreate, ProjectUpdate, ProjectOut）
- [x] 后端项目 service（create/get/list/update/delete，owner_id 隔离）
- [x] 后端项目 router（GET/POST /projects, GET/PUT/DELETE /projects/{id}）
- [x] 后端所有权鉴权（非 owner 返回 404，无 Token 返回 401）
- [x] 前端 api/project.ts（list/create/get/update/delete）
- [x] 前端 ProjectList 页面（卡片列表，删除确认）
- [x] 前端 ProjectCreate 页面（表单：名称/主题/类型/章节数/字数）
- [x] 前端 ProjectDetail 页面（详情展示 + 基础编辑）
- [x] 前端路由（/projects, /projects/create, /projects/:id）
- [x] 前端编译通过
- [x] docs/API_SPEC.md 项目接口更新

## 待办事项

### 章节 API（CRUD）闭环

- [x] 后端章节 schemas（ChapterCreate, ChapterUpdate, ChapterOut）
- [x] 后端章节 service（create/get/list/update/delete，project_id 关联 + owner_id 隔离）
- [x] 后端章节 router（嵌套路由 list/create + 独立路由 get/update/delete）
- [x] 后端 asyncpg UUID 兼容修复
- [x] 前端 api/chapter.ts（list/create/get/update/delete）
- [x] 前端 ProjectDetail 页面集成章节管理（列表/新建/编辑/删除）
- [x] 前端编译通过
- [x] docs/API_SPEC.md 章节接口更新

## 待办事项

### 任务系统 + 异步任务桩 + 资产读写 闭环

- [x] tasks 表 migration（Alembic 自动生成并应用）
- [x] 后端 Task 模型/ schemas / service / router
- [x] 后端 Generate router（桩）：architecture / directory / chapter
- [x] 后端 Assets router：GET / PUT /projects/{id}/assets/{type}
- [x] 后端路由挂载（main.py）
- [x] 前端 api/task.ts
- [x] 前端 api/asset.ts
- [x] 前端编译通过
- [x] docs/API_SPEC.md / DATA_MODEL.md 更新

### 前端项目工作台 Tab 页面

- [x] ProjectDetail 重构为 Tab 布局（概览/架构/目录/章节）
- [x] 架构 Tab：asset 读写 + AI 生成任务触发
- [x] 目录 Tab：asset 读写 + AI 生成任务触发
- [x] 章节 Tab：章节 CRUD 完整迁移
- [x] 前端编译通过

### 接入真实 LLM Architecture 生成

- [x] 复用 AI_NovelGenerator prompt 模板
- [x] 异步 LLM Adapter（httpx OpenAI-Compatible）
- [x] generation_service.py：5 步 architecture pipeline（异步改造）
- [x] task_service.py：run_architecture_task() 后台编排
- [x] generate.py：创建任务 + asyncio.create_task() 触发后台执行
- [x] config.py：LLM 默认配置项
- [x] 后端 import 验证通过

### 接入真实 LLM Directory 生成

- [x] 复用 blueprint prompt 模板
- [x] 复用 chapter_directory_parser 解析器
- [x] generation_service.generate_directory() + parse_chapter_blueprint()
- [x] task_service.run_directory_task() + chapters 表初始化
- [x] generate.py router 触发后台执行
- [x] 后端 import 验证通过

## 待办事项

### 接入真实 LLM Chapter 生成

- [x] 复用 `AI_NovelGenerator/prompts/chapter_prompts.py` → `backend/app/generator/prompts.py`（MVP 简化版：first_chapter_draft_prompt / next_chapter_draft_prompt）
- [x] 新增 `generation_service.generate_chapter_draft()` —— 读取 architecture + directory + previous chapter → LLM 生成单章正文
- [x] 更新 `task_service.py` —— 新增 `run_chapter_task()`：状态流转 → 读取前置资产 → 调用 generation_service → 写入 chapters.draft
- [x] 更新 `generate.py` —— chapter 接口创建任务后触发 `asyncio.create_task(run_chapter_task())`
- [x] 后端 import 验证通过
- [x] 前端章节列表增加 "AI 生成" 按钮（每章独立触发）
- [x] 前端任务状态轮询机制（`pollTask` 辅助函数，3 秒轮询 `getTask`，success/failed 自动停止）
- [x] 架构/目录/章节生成完成后自动刷新对应数据（替代 alert）
- [x] 前端编译通过

### 短剧改编 API（异步任务桩）

- [x] 新增 `drama_episodes` 表（Alembic migration 自动生成并应用）
- [x] 后端 DramaEpisode 模型：`backend/app/models/project.py`
- [x] 后端 DramaEpisode schema：`backend/app/schemas/drama.py`
- [x] 后端 Drama router：`backend/app/routers/drama.py` —— GET /projects/{id}/drama-episodes
- [x] 后端 Generate router 新增 drama-plan / drama-episode 触发端点
- [x] 后端 task_service 新增 `run_drama_plan_task()` / `run_drama_episode_task()`（桩任务，生成占位数据）
- [x] 后端 main.py 挂载 drama 路由
- [x] 前端 `frontend/src/api/drama.ts` —— listDramaEpisodes
- [x] 前端 ProjectDetail 新增"短剧改编"Tab：生成改编计划 + 单集脚本生成 + 任务轮询
- [x] 前端编译通过
- [x] docs/API_SPEC.md / DATA_MODEL.md 更新

## 待办事项

- [x] 角色状态追踪（update_character_state_prompt + task_service 读写 characters asset）
- [x] 接入真实 novel_to_drama LLM 生成（episode_mapper + script_generator prompt 复用）
- [x] 导出 API（JSON / Markdown / CSV）
- [x] 导出选择 + 批量导出（章节/剧集均支持复选框多选 + 批量导出 MD/JSON）
- [x] 脚本生成章节选择（生成脚本前弹出章节选择器，支持自定义来源章节）
- [x] 续集记忆机制（自动生成前集上下文摘要注入 prompt，保证角色/道具/剧情一致性）
- [x] 短剧改编 Tab 重构：模块化 EpisodeCard + ScriptViewer + 章节映射管理 + 大纲内联编辑
- [x] 后端新增 PUT outline/script/source-chapters 接口
- [x] 前端编译通过

### Bug 修复与体验优化（系统修缮）

- [x] 修复短剧改编状态同步：plan_task 设置 `"outlined"`，episode/batch_task 设置 `"script_ready"`
- [x] 修复章节选择器默认范围解析：新增 `parseSourceChapters()` 支持 `"第1-3章"` / `"第1章"` / `"1,2,3"` 格式
- [x] 全局主题改为暖色浅色背景（`#faf8f5` → `#f0ebe4` → `#e8e2d9`）
- [x] 玻璃面板精细化：圆角 2rem → 1rem，阴影调整，透明度 0.7 → 0.65
- [x] 字体层次规范化：`text-[10px]` → `text-xs`，移除中文不适用的 `tracking-widest`
- [x] 状态色板统一：slate / indigo / amber / emerald 四色体系
- [x] 工作流进度条：Tab 上方四步指示器（架构→目录→章节→短剧改编），可点击跳转
- [x] 短剧 Tab 空状态引导卡片：图标 + 两步流程图解 + CTA
- [x] 禁用按钮持续提示："AI 批量生成全部脚本"禁用时显示 `"请先生成改编计划"`
- [x] Tab 导航增强：激活态底色高亮 + 悬停反馈
- [x] 前端编译通过，服务重启正常

### AI 问答功能

- [x] 后端：新增 `chat_sessions` + `chat_messages` 模型
- [x] 后端：Alembic migration `d512a3fe455d` 自动生成并成功应用
- [x] 后端：新增 `backend/app/schemas/chat.py`
- [x] 后端：新增 `backend/app/services/chat_service.py`（CRUD + LLM 调用 + 项目上下文注入）
- [x] 后端：扩展 `llm_adapter.py` 新增 `invoke_messages()` 支持多轮对话
- [x] 后端：新增 `backend/app/routers/chat.py`（5 个 REST 接口）
- [x] 后端：`main.py` 挂载 chat 路由
- [x] 前端：新增 `frontend/src/api/chat.ts`
- [x] 前端：新增 `frontend/src/components/AIChatDrawer.tsx`（右侧抽屉、消息列表、快捷问题、会话管理）
- [x] 前端：`ProjectDetail.tsx` 集成 AI 助手入口按钮 + 抽屉组件
- [x] 前端 TypeScript 编译通过
- [x] 后端服务启动正常
- [x] docs/API_SPEC.md / DATA_MODEL.md / CHANGELOG.md 同步更新

### P0 核心体验优化

- [x] Auth 路由守卫 + 全局 Toast：未登录用户重定向 /login，API 错误统一 Toast 提示
- [x] 未保存修改警告：编辑中切换 Tab 或刷新页面时 confirm 确认
- [x] ProjectDetail.tsx 拆分：1777 行 god component → 5 个 Tab 子组件 + utils + 主壳
  - [x] `OverviewTab.tsx` — 项目信息编辑/展示
  - [x] `ArchitectureTab.tsx` — 架构编辑 + AI 生成
  - [x] `DirectoryTab.tsx` — 目录编辑 + AI 生成
  - [x] `ChaptersTab.tsx` — 章节列表 + CRUD + 搜索 + 批量导出
  - [x] `DramaTab.tsx` — 短剧改编 + 剧集管理 + 批量导出
  - [x] `utils.tsx` — 共享工具（pollTask, ProgressBar, statusBadge 等）
  - [x] `index.tsx` — 主壳：状态管理 + Header + Tab 切换 + 模态框
- [x] 前端编译通过，构建成功

### P1 代码质量优化

- [x] React Query 基础设施：`queryClient.ts` + `QueryClientProvider` 包裹 App
- [x] ProjectList 接入 React Query：`useQuery` 获取项目列表，`useMutation` 删除项目，自动刷新
- [x] 清理空目录：`hooks/`、`types/`（删除）
- [x] 删除死代码：`Dashboard.tsx` 页面（未在路由中引用）
- [x] 创建 `usePollingTask` hook：替代内联 `pollTask`，支持自动清理
- [x] 前端编译通过，零警告
- [x] 新建项目后列表自动刷新：ProjectCreate `useMutation` 成功时 `invalidateQueries(['projects'])`
- [x] "资产不存在" UX 优化：
  - 后端 `assets.py` 错误文案改为 `"该内容尚未生成"`
  - 前端所有导出路径（`handleExportAsset` / `handleExportChapters` / `handleExportEpisode` / `handleExportEpisodesBatch`）404 时弹出 `warning` Toast 而非红色错误条
  - 架构 Tab 加载时 404 静默处理，不显示报错

### P0 内核一致性修复

- [x] **第1章注入角色状态**：`first_chapter_draft_prompt` 增加 `{character_state}` 占位符，`generate_chapter_draft` 第1章时也传入角色状态，确保开篇角色形象与后续章节一致
- [x] **扩大前文衔接上下文**：`previous_chapter_draft[-500:]` → `[-1500:]`，同时新增 `{previous_chapter_summary}` 双轨输入（前一章概要 + 结尾片段），显著降低"遗忘伏笔"概率
- [x] **架构一致性校验（第6步）**：Pipeline 新增 Step6，用 LLM 审查核心种子/角色动力学/角色状态/世界观/情节架构五要素之间的矛盾，发现不一致时记录 warning 日志
- [x] 后端 import 验证通过，前端构建零警告

### P1 内核质量优化

- [x] **Temperature 分类控制**：设定类生成（架构/目录/角色状态）降至 0.3，章节正文保持 0.6，一致性校验降至 0.2，减少设定漂移
- [x] **目录解析器鲁棒性增强**：支持 4 种标题格式备选正则（`第1章 - [标题]` / `第1章 [标题]` / `第1章：标题` / `Chapter 1`），解析失败时抛出明确错误而非静默跳过
- [x] **章节生成后一致性检查**：每章生成后自动审查是否与角色状态/前文情节矛盾（已死亡角色重现、道具无故恢复等），发现问题记录 warning
- [x] 后端 import 验证通过，前端构建零警告

### P2 结构化世界状态记忆（长程一致性基础设施）

- [x] **Genre Templates**：`backend/app/generator/world_state_templates.py`
  - 新增 `GENERIC_TEMPLATE` / `XIANXIA_TEMPLATE` / `URBAN_TEMPLATE`
  - `get_template(genre)` 按 genre 字符串匹配返回对应模板
- [x] **Delta Extraction Prompt**：`extract_world_state_delta_prompt` —— LLM 从章节正文中提取结构化变更（JSON delta）
- [x] **State Summary Prompt**：`build_state_summary_prompt` —— LLM 筛选 5-10 条最相关状态点注入下一章 prompt
- [x] **Generation Service 扩展**：`backend/app/services/generation_service.py`
  - 新增 `_parse_llm_json()`：鲁棒 JSON 提取（去 markdown 代码块、补全截断括号）
  - 新增 `extract_world_state_delta()`：异步 LLM 调用提取 delta
  - 新增 `merge_world_state()`：深合并 + 变更历史记录（old → new）
  - 新增 `build_state_summary()`：异步 LLM 调用生成状态摘要
  - `generate_chapter_draft()` 新增 `world_state_summary` 参数，追加到 character_state 后注入 prompt
- [x] **Task Service 集成**：`backend/app/services/task_service.py`
  - `run_chapter_task()` / `run_batch_chapters_task()`：
    - 生成前读取 `world_state` asset，调用 `build_state_summary()` 构建摘要
    - 生成后调用 `extract_world_state_delta()` 提取变更
    - 无变更时跳过写入，有变更时 `merge_world_state()` 并保存回 asset
  - 向后兼容：无 world_state asset 时自动初始化空结构
- [x] **前端「角色与世界」Tab**：`frontend/src/pages/ProjectDetail/WorldStateTab.tsx`
  - 读取 `world_state` asset，解析 JSON
  - 角色/事件/世界设定三栏卡片展示
  - 变更历史时间线（按章节倒序，显示 old → new）
  - 空状态引导：未生成章节时显示友好提示
- [x] **Tab 集成**：`frontend/src/pages/ProjectDetail/index.tsx`
  - TabKey 新增 `'worldstate'`
  - tabs 数组新增 `{ key: 'worldstate', label: '角色与世界' }`
  - 条件渲染 `<WorldStateTab projectId={...} />`
- [x] 后端 import 验证通过，前端构建零警告

### P2 后端生成质量与稳定性优化

- [x] **修复 world_state_summary 未注入 prompt**：`first_chapter_draft_prompt` / `next_chapter_draft_prompt` 新增 `{world_state_summary}` 占位符，`generate_chapter_draft` 将摘要独立传入（不再拼接到 character_state），避免重复且让 LLM 明确识别世界状态约束
- [x] **Prompt 写作要求强化**：新增"必须严格遵循世界状态摘要，禁止矛盾情节"的明确约束（已死亡角色不得出场、已损坏物品不得完好等）
- [x] **LLM 输出清洗精确化**：`_invoke_with_retry` 从全局 `replace("```", "")` 改为正则只去除首尾 markdown 代码块标记（`^```[\w]*\n?` 和 `\n?```\s*$`），避免误删正文中的代码片段或类似标记
- [x] **merge_world_state 无副作用**：新增 `copy.deepcopy(delta)`，防止 `fields.pop("changed_fields")` 修改传入参数
- [x] **build_state_summary Token 精简**：`slim_state` 除 history 截断为最近 3 章外，characters/events/world 每类限制最多 10 个条目，优先保留最近有变更的实体，防止长程状态膨胀导致 prompt 超限
- [x] **批量生成错误隔离**：`run_batch_chapters_task` 循环内包裹单章 try/except，单章失败记录到 `failed_chapters` 后继续生成后续章节，任务结果报告成功/失败明细（含章节号和错误信息）
- [x] **新增单元测试**：`backend/app/tests/test_world_state.py` 覆盖模板选择、JSON 解析鲁棒性、状态合并与变更历史，21 用例全部通过
- [x] 后端 import 验证通过，前端构建零警告

## 待办事项

### ProjectDetail React Query 深度替换（已完成）

- [x] 新增 `useProjectData` hook：集中封装项目详情 / 章节列表 / 资产 / 短剧剧集的 `useQuery` 与保存操作的 `useMutation`
- [x] `index.tsx` 移除 5 个手动数据获取 `useEffect`，改为从 hook 读取；任务完成后改为 `queryClient.invalidateQueries` 自动刷新
- [x] `ArchitectureTab` / `DirectoryTab` props 精简：`setXxxText` 改为 `value` + `onChange`，组件不再直接操作外部 state
- [x] `WorldStateTab` 移除手动 `useEffect` + `useState`，改为 `useQuery(['asset', id, 'world_state'])`
- [x] 各 Tab 保存操作接入 `useMutation`，成功后自动 `invalidateQueries`，无需手动 setState
- [x] 前端构建零警告

### 生产部署准备

- [x] `backend/Dockerfile` —— 多阶段构建生产镜像（Python 3.12 slim）
- [x] `railway.toml` —— Railway 部署配置（自动迁移 + 健康检查 + 重启策略）
- [x] `backend/app/main.py` —— CORS 支持 `CORS_ORIGINS` 环境变量
- [x] `backend/.env.example` —— 补充 `FERNET_SECRET`、`LLM_*`、`CORS_ORIGINS`
- [x] `frontend/.env.example` —— 补充生产环境 API 地址说明
- [x] `docs/DEPLOYMENT.md` —— Railway + Vercel 部署完整指南
