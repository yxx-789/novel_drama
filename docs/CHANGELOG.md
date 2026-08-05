# 变更日志

## [未发布]

### V3 P1：积木式生成

- **7 维正交积木库（用户层）**
  - `backend/app/generator/block_library.py` 新增用户层积木库：核心题材（12）、故事背景（8）、核心卖点（11）、叙事结构（7）、文风基调（8）、目标受众（7）、角色规模（6），每块积木含 `label` + 完整有深度的 `prompt_fragment`（文风特征 / 卖点套路 / 典型场景 / 避雷 / 伏笔手法倾向等）
  - 每块 prompt_fragment 均非空且长度达标（单元测试强制 `>= 50` 字）；未知选项降级为原文直述，不丢信息不崩溃
  - 多选维度（背景 / 卖点）支持数组值，逐项注入各选项 prompt_fragment 核心内容；单选维度注入完整片段
  - 12 个核心题材各配一份「默认配方」（DEFAULT_RECIPES，与前端 `frontend/src/constants/blocks.ts` 一致），选题材自动带出其余 6 维

- **内部细粒度风味层（internal_flavor）**
  - 每个核心题材内置一组 5-8 个「内部风味」块（如玄幻的洪荒色彩 / 高武 / 乱世争霸），随机掷 1-3 个，紧跟核心题材段注入，题材内差异化

- **写作上下文 + 创作意图注入所有生成环节**
  - `generation_service._prompt_context_for_project()` 把用户 `writing_config` 拼成「写作上下文」（`build_context`），剧情走向作为「创作意图」高优先注入
  - 架构（核心种子 / 角色动力学 / 世界观 / 情节架构 / 角色状态）、目录（章节蓝图）、章节正文（首章 / 续章）全部 prompt 新增【写作上下文】与【创作意图】段；创作意图冲突时以此为准
  - 未填剧情走向时回退占位符兜底文本，保证【创作意图】段不悬空

- **减法 prompt：硬规则已删、轻骨架保留**
  - 角色动力学 prompt 删除「3-6 个核心角色」上限，角色规模交给用户选择的 cast_scale 积木
  - 情节架构 prompt 删除硬编码三幕式结构（第一幕 / 第二幕 / 第三幕各阶段固定要求），改为「剧情推进起落节奏 + 伏笔铺垫回收方案 + 不必为结构而结构」的轻骨架
  - 章节蓝图删除「每 3-5 章一个悬念单元」「认知颠覆 ★ 强度」硬规则，改为按剧情自然划分章节集群、以「悬念密度」表达节奏
  - 首章 prompt 删除「不要写总结性结尾，要在悬念最高点自然收束」的硬性收尾要求

- **Project 模型与 API**
  - `Project` 新增 `writing_config`（JSONB）列（Alembic migration `f210059ee189_add_project_writing_config.py`）；`ProjectCreate` / `ProjectUpdate` / `ProjectOut` 支持存取

- **前端创建页**
  - `frontend/src/pages/ProjectCreate.tsx` 新增「核心题材 + 故事背景 + 核心卖点 + 叙事结构 + 文风基调 + 目标受众 + 角色规模」7 维表单、剧情走向输入、自定义设定（核心卖点 / 独特设定 / 角色要求 / 避雷 / 自由补充）与默认配方自动带出

- **单元测试**
  - `backend/app/tests/test_block_library.py` 覆盖积木库完整性（非空 / 长度达标 / label 齐全 / 默认配方覆盖全部题材 / 内部风味合法 / build_context 正确性 / 多选数组 / 未知项降级）

### 写作配置冲突规则引擎

- **规则数据 + 检测函数（后端唯一真源）**
  - `backend/app/generator/block_library.py` 新增冲突规则段：背景世界系分组（古风 / 山野中性 / 现代 / 未来）、题材硬禁背景系（历史禁现代/未来，体育禁古风/未来）、硬冲突规则（HARD_CONFLICTS）、软警告规则（SOFT_WARNINGS）
  - 检测函数 `check_hard_conflicts` / `check_soft_warnings` / `validate_writing_config` 统一兼容字符串 / 数组取值，缺失维度视为未选、未知取值不崩溃；`validate_writing_config` 汇总 hard + soft，`valid = 无硬冲突`（软警告不阻断）
  - 硬冲突覆盖：背景跨系（非中性世界系多选并存）、题材×背景系、精简卡司×群像交织、金手指系统×打脸爽感（无敌×打脸）、娇软治愈×女强飒爽（内部风味互斥）
  - 软警告覆盖：罕见融合（如仙侠×末世废土）、卖点错位、文风×受众、文风×题材、结构×受众、规模×题材、结构×背景、重生×穿越冗余、剧情走向×设定（关键词 vs 背景系）

- **创建时校验（硬冲突 400）**
  - `project_service.create_project` 在掷内部风味前用 `validate_writing_config` 校验用户原始选择：硬冲突抛 `ValueError` → `routers/projects.py` 转 HTTP 400 返回冲突文案；软警告不阻断、仅记日志；无 writing_config（旧项目）跳过

- **前端实时灰禁 + 弹确认**
  - `frontend/src/constants/conflicts.ts` 新增规则轻量副本（与后端数据保持一致，后端为准）；`frontend/src/pages/ProjectCreate.tsx` 实时检测：题材硬禁世界系与跨世界系背景置灰（山野中性系除外）、精简卡司禁选群像交织、群像交织反向禁选精简卡司、金手指系统×打脸爽感互斥置灰
  - 软冲突通过 `window.confirm` 询问是否继续（不阻断）；提交前再做一次硬冲突检查，命中则阻止提交并展示冲突项

- **单元测试**
  - `backend/app/tests/test_project_service.py` 覆盖：硬冲突创建被拒（精简×群像 / 历史×都市霓虹）、软警告不阻断（仙侠×末世废土，正常创建并写回 internal_flavor）、无冲突 / 空 / 缺失 config 正常创建、plot_direction 剧情走向×设定软警告不阻断

### 灵感策展（LLM 策展 + 加权排序）

- **LLM 策展**：采集器在入库前先取正文，再让 LLM 判断创作价值，只保留有叙事潜力的热点并附灵感点与质量分
  - `scripts/xhs_hot_collector.py` 每分类按互动热度取 Top N，再取前 K 条进入策展：`fetch_detail()` 取正文（截断 2000 字）→ `_llm_curate()` 单次请求批量输出 `[{i, usable, inspiration_hint, quality_score}]`
  - `usable=false` 直接过滤不入库；`usable=true` 带上灵感点（`inspiration_hint`）与 1-5 创作价值分（`quality_score`，依据人物冲突 / 戏剧情境 / 情感张力 / 意外转折等叙事潜力）
  - 未配置 `LLM_API_KEY` 或 LLM 调用失败时全部放行（无灵感点、质量分 0），保证采集链路不中断
  - 采样量可用环境变量调整：`TOP_N_PER_CATEGORY`（默认 20）、`CURATE_TOP_PER_CATEGORY`（默认 8）

- **加权排序**：新增 `compute_rank_score()`，`rank_score = likes×1.0 + collects×1.2 + shares×1.5 + comment_count×2.0 + quality_score×300`；`GET /api/inspiration/hot` 改为按 `rank_score` 降序（同分按点赞降序）

- **hot_topics 新列**：Alembic migration `d8c4a212986c_add_inspiration_curation_columns.py` 新增 `comment_count` / `inspiration_hint` / `quality_score` / `rank_score`（`server_default` 回填存量行后移除默认值）；`backend/app/models/inspiration.py` HotTopic 同步新增 4 列

- **前端灵感点展示**：`frontend/src/pages/ProjectDetail/InspirationTab.tsx` 热点卡片在 `inspiration_hint` 非空时展示 💡 灵感点；`frontend/src/api/inspiration.ts` `HotNote` 类型新增 `comment_count` / `inspiration_hint` / `quality_score` 字段

### 主页创作灵感 + 主页 AI 助手

- **主页创作灵感区（完整复用 InspirationTab）**
  - `frontend/src/pages/ProjectList.tsx` 顶部新增「创作灵感」glass-panel 区块，直接挂载 `InspirationTab`
  - 完整复用项目内 Tab 的组件能力（分类 chips / 关键词搜索 / 刷新 / 热点列表），非缩水版
  - 无项目上下文时，热点按钮文案为「用它创建项目」：携带 note_id / topic / summary / likes / author / url 跳转创建页

- **创建页预填 + 自动导入**
  - `frontend/src/pages/ProjectCreate.tsx` 读取 query 参数预填项目名称与主题
  - 创建成功后自动调用 `POST /api/projects/{id}/inspiration` 导入灵感（幂等覆盖，设为项目主题并写入 inspiration 资产）

- **主页 AI 助手（AIChatDrawer 通用模式）**
  - `AIChatDrawer` 的 `projectId` 改为可选：无项目上下文时调用 `listUserChatSessions` / `createChatSession()`（project_id 为 null）
  - 通用快捷问题（构思开头 / 推荐题材 / 甜宠新意 / 点子成书）替代项目内快捷问题
  - 后端 `chat_service._get_project_context()` 在无 project_id 时不注入项目上下文，仅作通用对话
  - 行为不变：项目内「创作灵感」Tab 仍为「导入项目」；项目内 AI 助手仍带项目上下文

### 创作灵感功能

- **hot_topics 热点表**
  - Alembic migration `81909d23eb6a_add_hot_topics_table.py` 生成并成功应用
  - 后端模型：`backend/app/models/inspiration.py` —— HotTopic（category / note_id / title / summary / likes / collects / shares / url / author / source / fetched_at）
  - `note_id` 唯一约束 `uq_hot_topics_note_id`；`category`、`fetched_at` 建立索引
  - 采集器按 `note_id` 幂等 upsert（`ON CONFLICT (note_id) DO UPDATE`）

- **3 个灵感 API（均需 JWT 鉴权）**
  - `GET /api/inspiration/categories` —— 返回预设灵感分类名列表（唯一真源：`backend/app/core/preset_categories.py`，32 个分类，采集器与后端共用）
  - `GET /api/inspiration/hot` —— 返回最近一批（`fetched_at` 为最新批次）热点，按点赞降序；支持 `category` / `keyword` 过滤、`limit`（默认 20，上限 50）
  - `POST /api/projects/{id}/inspiration` —— 一键导入：设为项目主题并写入 `inspiration` 资产（幂等覆盖），返回 `{success, topic}`
  - `GET /api/inspiration/hot` 响应包含 note_id / title / summary / likes / collects / comment_count / inspiration_hint / quality_score / author / fetched_at，**不含 source / url 字段**

- **热点采集器脚本（每日一次）**
  - 新增 `scripts/xhs_hot_collector.py` —— 通过 MCP 服务搜索各分类关键词 → 规范化 → 批量 upsert 写入 `hot_topics`
  - 新增 `scripts/mcp_client.py` —— MCP 客户端封装；`scripts/test_collector.py` —— 采集器测试
  - 新增 `scripts/launchd.example.plist` —— 每日 8:30 定时执行示例

- **前端「创作灵感」Tab**
  - 新增 `frontend/src/api/inspiration.ts` —— 3 个 API 封装
  - 新增 `frontend/src/pages/ProjectDetail/InspirationTab.tsx` —— 分类筛选 / 关键词搜索 / 刷新、热点列表、一键导入设主题
  - `ProjectDetail/index.tsx` 新增 `inspiration` Tab（创作灵感）

- **生成注入「创作灵感参考」**
  - `inspiration_service.build_inspiration_guidance()` 读取项目已导入的灵感资产，格式化为创作引导
  - 架构 / 目录生成任务（`run_architecture_task` / `run_directory_task`）在 LLM 生成前将引导注入 `user_guidance`

- 全程前端/API 不暴露热点来源平台（`source` 仅存于数据库，不对外暴露）

### 配置与模型（DeepSeek 接入）

- 平台默认 LLM 切换为 **DeepSeek**：
  - `LLM_BASE_URL=https://api.deepseek.com`、`LLM_MODEL=deepseek-chat`、`LLM_MAX_TOKENS=8192`
  - 同步更新：`backend/.env.example`、`backend/app/core/config.py` 默认值、前端 AI 设置抽屉占位提示、`docs/API_SPEC.md` 示例

### 修复

- **生成任务长时间无输出（架构生成 5 分钟卡死）**：`deepseek-v4-flash` 是重度推理模型，在 `max_tokens=2048` 下把全部 token 消耗在 `reasoning_content`（思考过程）上，导致 `content` 返回空，`_invoke_with_retry` 反复重试（每次失败前模型还要思考 20-90 秒），5 步串行的架构管线累计 5 分钟以上无结果
  - 实测：v4-flash 在 2048 预算下 `content`=0 字、reasoning=7111 字；`deepseek-chat` 39s 完整输出 5366 字（`finish=stop`）
  - 修复：`LLM_MODEL` 切换为 `deepseek-chat`（非推理、直接输出正文），`LLM_MAX_TOKENS` 从 2048 提升到 8192（章节草稿约需 3000 token，避免截断）
- **世界状态功能失效（连续 3 个缺陷，已逐一修复并实测通过）**
  - ① `generation_service.py` 模块顶层缺少 `import json`，`extract_world_state_delta` / `build_state_summary` 中 `json.dumps` 触发 `NameError`，被 try/except 吞掉导致任务"成功"但世界状态从未更新 → 顶层新增 `import json`
  - ② `extract_world_state_delta_prompt` 模板内嵌字面 JSON 示例的 `{}` 未转义，`prompt.format()` 抛 `KeyError`（错误信息：`KeyError: '\n  "changed_in_chapter"'`）→ 结构花括号转义为 `{{}}`，保留 `{chapter_number}` 占位符
  - ③ `merge_world_state` 将所有 category 按"实体嵌套"处理，但 `world` 实际为扁平结构（`字段->值`），遍历到 `changed_fields` 的 list 值时 `TypeError: pop expected at most 1 argument` → 兼容扁平/嵌套两种结构
  - 验证：真实 LLM 调用 extract → merge → build_state_summary 全链路 PASS；`test_world_state.py` 新增 2 个回归用例，23 个测试全部通过
- **后端启动崩溃（EmailStr）**：`schemas/user.py` 使用 `pydantic.EmailStr` 需要 `email-validator`，requirements.txt 未包含导致 uvicorn 启动即崩溃
  - 修复：`backend/requirements.txt` 新增 `email-validator>=2.0.0`
- **注册接口 500（bcrypt 兼容）**：passlib 1.7.4 与 bcrypt 5.x 不兼容（新版删除 `__about__` 属性，密码哈希失败）
  - 修复：`backend/requirements.txt` 钉住 `bcrypt==4.0.1`

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
