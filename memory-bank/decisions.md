# 关键决策记录

## 决策格式

每条决策包含：
- **背景**：当时面临的问题
- **选项**：考虑过哪些方案
- **决策**：最终选择
- **理由**：为什么选这个
- **影响**：对后续开发的影响
- **可逆性**：如果后续发现错误，是否容易回退

---

## D001：技术栈选型 —— 后端框架

| 字段 | 内容 |
|------|------|
| **背景** | 需要选择 Web 后端框架，旧项目均为纯 Python |
| **选项** | A. FastAPI；B. Flask；C. Django；D. 全栈 Python 框架（Reflex/Streamlit） |
| **决策** | **FastAPI** |
| **理由** | 1. 原生异步支持，适合 I/O 密集型 LLM 调用；2. 自动生成 OpenAPI 文档，前后端对接成本低；3. SQLAlchemy 2.0 生态成熟；4. 与部署平台（Railway/Render）兼容性好 |
| **影响** | 所有后端代码基于此框架开发，路由、依赖注入、中间件均按 FastAPI 模式组织 |
| **可逆性** | 低。但 FastAPI 是业界标准选择，回退可能性小 |

---

## D002：技术栈选型 —— 前端框架

| 字段 | 内容 |
|------|------|
| **背景** | 需要选择前端技术栈，用户倾向纯 Python 生态以降低维护成本 |
| **选项** | A. React + TypeScript；B. Vue；C. Reflex（全栈 Python）；D. Streamlit |
| **决策** | **React + TypeScript** |
| **理由** | 1. Vercel 等部署平台对 React 有一键部署支持；2. 复杂协作界面需要成熟组件生态（如表格编辑、Markdown 预览）；3. 前后端严格分离，前端只负责 UI，业务逻辑在后端 Python，维护成本可控；4. Reflex/Streamlit 适合原型，不适合生产级交互 |
| **影响** | 前端独立项目，通过 REST API 与后端通信；状态管理用 Zustand，数据获取用 React Query |
| **可逆性** | 中。前端可独立替换为 Vue 或其他框架，只要 API 契约不变 |

---

## D003：数据库选型

| 字段 | 内容 |
|------|------|
| **背景** | 需要持久化存储用户、项目、章节、任务等数据 |
| **选项** | A. PostgreSQL；B. SQLite；C. MySQL；D. MongoDB |
| **决策** | **PostgreSQL** |
| **理由** | 1. 支持 JSONB 存储半结构化项目资产（project_assets），避免 MVP 阶段过度拆表；2. 托管服务成熟（Railway/Render/Supabase 均支持）；3. 全文搜索能力为 Phase 3 预留；4. SQLAlchemy 2.0 对 PostgreSQL 支持完善 |
| **影响** | 所有数据模型基于 PostgreSQL 设计，使用 JSONB 字段存储 project_assets |
| **可逆性** | 低。但 PostgreSQL 是标准选择 |

---

## D004：异步任务队列选型

| 字段 | 内容 |
|------|------|
| **背景** | LLM 生成任务耗时 30 秒至数分钟，必须异步化 |
| **选项** | A. RQ；B. Dramatiq；C. Celery；D. FastAPI BackgroundTasks |
| **决策** | **Celery + Redis** |
| **理由** | 1. Celery 是 Python 生态最成熟的分布式任务队列，社区文档完善；2. Redis 作为 broker 和 backend，与现有 Redis 缓存共用基础设施；3. 支持任务持久化、取消（revoke）、定时任务等能力，解决 `asyncio.create_task` 重启丢任务问题；4. 通过 `asyncio.run()` 包装层复用现有异步业务代码，迁移成本低；5. Docker Compose 一键启动 worker 服务，部署简单 |
| **影响** | Worker 进程独立运行，通过 Redis 与主服务通信；任务状态写入 generation_tasks 表 |
| **可逆性** | 高。任务执行逻辑封装在 Service 层，切换队列框架只需改 Worker 入口和入队方式 |

---

## D005：数据模型设计 —— project_assets 表

| 字段 | 内容 |
|------|------|
| **背景** | 旧项目产生大量半结构化数据（架构、目录、角色状态、世界规则、时间线等），如果每种都单独建表，MVP 阶段表数量膨胀 |
| **选项** | A. 每种资产单独建表（architecture / directory / character_state / world_rule / timeline...）；B. 统一 project_assets 表，用 asset_type 区分；C. 全部存 JSON 文件 |
| **决策** | **统一 project_assets 表，PostgreSQL JSONB 存储** |
| **理由** | 1. MVP 阶段减少表数量，降低维护成本；2. PostgreSQL JSONB 支持索引和查询，性能可接受；3. 旧项目的各类文本/JSON 输出都能容纳；4. 后续如有高频查询的特定资产类型，再拆分为独立表 |
| **影响** | 架构、目录、角色状态等均通过 (project_id, asset_type) 唯一键存取 |
| **可逆性** | 高。后续可将高频资产类型拆分为独立表，迁移逻辑简单 |

---

## D006：向量存储选型

| 字段 | 内容 |
|------|------|
| **背景** | AI_NovelGenerator 使用 Chroma 进行 RAG 检索，需要在新系统中保留此能力 |
| **选项** | A. Chroma（本地文件）；B. Qdrant（本地/云）；C. Pinecone（纯云）；D. PostgreSQL pgvector |
| **决策** | **MVP 用 Chroma 本地持久化，后续评估 Qdrant** |
| **理由** | 1. 旧项目已有 Chroma 使用经验，adapter 可直接复用；2. MVP 阶段单实例部署足够；3. 做抽象层封装，后续迁移到 Qdrant 无需改业务代码；4. pgvector 对长文本嵌入支持不如专用向量库 |
| **影响** | 向量库存储在服务器本地磁盘，按 project_id 隔离目录 |
| **可逆性** | 高。已设计抽象层，切换实现只需改 infra/vectorstore.py |

---

## D007：认证方案

| 字段 | 内容 |
|------|------|
| **背景** | Web 产品需要用户认证 |
| **选项** | A. JWT + 自建注册登录；B. OAuth（GitHub/Google）；C. Session Cookie |
| **决策** | **JWT + 自建注册登录** |
| **理由** | 1. MVP 阶段简单直接，不依赖第三方 OAuth 配置；2. JWT 无状态，适合前后端分离和部署平台环境；3. Phase 2 可扩展 OAuth 登录；4. 密码用 bcrypt 哈希，安全性可接受 |
| **影响** | 前端存储 Token（localStorage），每次请求携带 Authorization 头 |
| **可逆性** | 中。后续可加 OAuth，JWT 体系本身兼容 |

---

## D008：部署方案

| 字段 | 内容 |
|------|------|
| **背景** | 用户希望上传到 GitHub 并使用常用部署平台 |
| **选项** | A. Vercel + Railway；B. Vercel + Render；C. 自建服务器；D. 容器编排（K8s） |
| **决策** | **前端 Vercel + 后端 Railway/Render** |
| **理由** | 1. Vercel 对 React 项目零配置部署；2. Railway/Render 支持 Python + PostgreSQL + Redis 一键部署；3. 与 GitHub 集成，push 即部署；4. 免费额度足够 MVP 阶段使用；5. 无需维护服务器 |
| **影响** | CI/CD 通过 GitHub Actions 或平台原生集成实现 |
| **可逆性** | 高。前后端分离架构，可迁移到任何云服务商 |

---

## D009：MVP 范围 —— 单人优先

| 字段 | 内容 |
|------|------|
| **背景** | 产品面向 2-4 人团队，但 MVP 资源有限 |
| **选项** | A. MVP 直接做团队协作；B. MVP 先做单人闭环，Phase 2 加协作 |
| **决策** | **MVP 先做单人闭环** |
| **理由** | 1. 核心生成逻辑（小说→短剧）与单人/多人无关，先验证价值；2. 协作功能（权限、编辑锁、冲突解决）是独立复杂度，不阻塞核心流程；3. 单人 MVP 可更快上线获取反馈；4. 数据库已预留 project_members 结构，Phase 2 平滑扩展 |
| **影响** | Phase 1 不做成员邀请、权限控制、编辑锁；项目按 owner_id 隔离 |
| **可逆性** | 高。协作是增量功能，不影响已有单人流程 |

---

## D010：短剧改编数据存储

| 字段 | 内容 |
|------|------|
| **背景** | novel_to_drama 输出分镜头脚本，数据层级为：改编项目 → 集 → 场景 → 镜头 |
| **选项** | A. 全部扁平化存 JSON；B. drama_projects + drama_episodes + drama_scripts 三表；C. 两表（episodes 存 JSON，scripts 独立） |
| **决策** | **三表结构：drama_projects / drama_episodes / drama_scripts** |
| **理由** | 1. 分镜数据有明确的场景/镜头层级，关系型结构便于按集/场景查询；2. CSV 导出需要按行输出镜头，独立表更易组装；3. episodes 的 outline_json 用 JSONB 保持灵活；4. 三表结构清晰，不过度复杂 |
| **影响** | 短剧生成任务分两步：先生成 episode outline，再生成 scripts |
| **可逆性** | 中。scripts 表可合并为 JSONB，但独立表更利于查询 |

---

## D011：章节编辑存储 —— draft vs finalized

| 字段 | 内容 |
|------|------|
| **背景** | 章节有 AI 生成的草稿和用户编辑后的定稿，需要区分存储 |
| **选项** | A. 单字段 text，覆盖保存；B. draft + finalized_text 双字段；C. 版本历史表 |
| **决策** | **draft + finalized_text 双字段** |
| **理由** | 1. 保留草稿便于用户对比和回退；2. 定稿后才触发向量化、摘要更新等后续流程；3. 版本历史表 Phase 2 再做，MVP 双字段足够；4. status 字段标记流转状态（pending→draft→finalized） |
| **影响** | 章节定稿 API 将 draft 复制到 finalized_text，并触发后续处理 |
| **可逆性** | 高。后续可加版本历史表，双字段作为当前版本缓存 |

---

## D012：长程一致性 —— 世界状态结构化记忆

| 字段 | 内容 |
|------|------|
| **背景** | 章节数超过 10 章后，LLM 频繁遗忘角色能力、物品、境界等设定，产生强烈"AI 感"，尤其修仙/都市/系统文对一致性要求极高 |
| **选项** | A. 纯文本角色状态（已有方案，随章节增长膨胀且检索低效）；B. 向量检索 RAG（检索召回精度不稳定，适合参考不适合精确状态追踪）；C. 结构化 JSON 世界状态 + Delta 提取 + 摘要注入 |
| **决策** | **C. 结构化 JSON 世界状态** |
| **理由** | 1. 结构化数据精确可控，角色/事件/世界规则分门别类，避免纯文本的模糊性；2. Delta 提取只记录变更，避免每章全量重写导致的 token 浪费和幻觉；3. 状态摘要筛选 5-10 条最相关点注入 prompt，既保证上下文不超限，又确保关键信息不遗漏；4. 变更历史时间线可回溯，便于前端展示和人工校验；5. 不同 genre 用不同模板（修仙追境界/法宝，都市追资产/关系），贴合类型小说需求 |
| **影响** | 新增 `world_state` asset_type，generation_service 增加 3 个函数，task_service 单章/批量任务均集成状态读写，前端新增「角色与世界」Tab |
| **可逆性** | 高。`world_state_summary` 参数有默认值，不传入时不影响生成逻辑；旧项目无 world_state asset 自动初始化为空结构 |

---

## 待决策项

以下决策在开发过程中根据实际情况确定：

| 编号 | 议题 | 状态 |
|------|------|------|
| D012 | 任务队列最终选型（RQ vs Dramatiq vs Celery） | **已确定：Celery** |
| D013 | API Key 加密方案（Fernet / 环境变量） | 待 Phase 1 开发时确定 |
| D014 | 前端路由方案（React Router / TanStack Router） | 待 Phase 1 前端搭建时确定 |
| D015 | 任务进度通知方案（轮询 / SSE） | 待 Phase 1 开发时确定，MVP 先用轮询 |
