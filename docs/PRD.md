# AI 小说 & 短剧创作工作台 —— 项目计划书（修订版）

## 1. 项目定位

本项目是一个面向 **2-4 人小团队** 的 Web 创作工作台，用于整合两个已有本地 Python 项目：

- **小说生成项目**：AI_NovelGenerator
- **小说改编短剧脚本项目**：novel_to_drama

目标是将其整合为一个统一的 B/S 产品，提供从：

**小说创作 → 章节协作 → 短剧改编 → 导出**

的完整创作闭环。

### 1.1 产品定位

这是一个 **创作工作台**，不是泛化内容平台，不追求首版覆盖所有高级能力。

### 1.2 目标用户

- 2-4 人的小型内容创作团队
- 有小说创作与短剧改编需求的个人或小组
- 已有一定 AI 辅助创作习惯，希望从本地脚本升级到可协作网页工作台的用户

---

## 2. 项目目标

### 2.1 MVP 目标

第一版必须完成以下闭环：

- 用户可登录并创建小说项目
- 用户可生成小说架构、目录、章节
- 用户可编辑和保存章节内容
- 用户可基于小说内容生成短剧改编方案
- 用户可查看并导出短剧脚本
- 项目可本地运行，并可部署到云端

### 2.2 长期目标

在 MVP 跑通后，再逐步增加：

- 小团队协作能力
- 编辑锁 / 乐观锁
- 项目快照与版本恢复
- 结构化记忆与一致性检查
- 语义检索与高级搜索
- 更丰富的导出与工作流能力

---

## 3. 非目标（MVP 暂不实现）

以下能力不在第一版范围内：

- 实时多人协同编辑（OT / CRDT / Yjs）
- 复杂审稿流 / 审批流
- 多租户 SaaS 架构
- 高级 Agent 自动编排
- 复杂可视化图谱（角色关系图、时间线大屏）
- 复杂 WebSocket 全链路实时交互
- 高频自定义模型路由策略
- 企业级权限细粒度控制

---

## 4. 核心使用流程

### 4.1 小说创作流程

创建项目
→ 填写主题、类型、章节数等参数
→ 生成小说架构
→ 生成章节目录
→ 逐章生成正文
→ 手动编辑与定稿

### 4.2 短剧改编流程

选择小说项目
→ 生成改编计划
→ 确认集数、时长、节奏等参数
→ 生成分集脚本
→ 查看分镜脚本
→ 导出为 JSON / Markdown / CSV

---

## 5. 技术方案

### 5.1 总体架构

采用前后端分离架构：

- 前端：React + TypeScript
- 后端：FastAPI
- 数据库：PostgreSQL
- 异步任务：Redis + 任务队列
- 向量检索：抽象接口，MVP 默认 Chroma
- 部署：GitHub + 云平台自动部署

### 5.2 技术栈

#### 后端

- FastAPI
- SQLAlchemy 2.0
- Alembic
- Pydantic
- PostgreSQL
- Redis
- 任务队列：MVP 优先 RQ 或 Dramatiq；Celery 可选
- httpx

#### 前端

- React
- TypeScript
- Tailwind CSS
- Zustand
- React Query
- Axios

#### 检索与记忆

- 向量存储抽象层
- MVP 默认：Chroma
- 后续可迁移：Qdrant

#### 部署

- GitHub 作为主仓库
- 前端：Vercel
- 后端 + Worker + Redis + PostgreSQL：优先 Railway
- 备选：Render

---

## 6. 技术边界与冻结项

以下内容在 MVP 阶段视为冻结项，不轻易修改：

- 后端框架使用 FastAPI
- 数据库使用 PostgreSQL
- 前端使用 React + TypeScript
- 项目采用前后端分离
- 异步任务必须通过任务队列，不允许在 HTTP 请求中执行长耗时 LLM 任务
- 旧项目核心逻辑迁移到 service 层，不直接复用 CLI / GUI 入口
- 数据存储以数据库为主，不再依赖本地 JSON 文件作为业务主存储

---

## 7. 目录结构规划

```
ai-novel-studio/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── DATA_MODEL.md
│   ├── API_SPEC.md
│   └── CHANGELOG.md
├── memory-bank/
│   ├── project-context.md
│   ├── decisions.md
│   ├── progress.md
│   └── feature-notes/
├── AGENTS.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── infra/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   └── services/
│   ├── alembic/
│   ├── worker.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── store/
│   │   └── types/
│   └── package.json
├── prompts/
├── docker-compose.yml
└── README.md
```

---

## 8. 核心模块设计

### 8.1 后端模块

- **认证与用户**：注册、登录、当前用户信息、权限校验
- **项目管理**：项目创建、编辑、删除、项目状态管理、项目成员管理（Phase2）
- **小说生成模块**：生成架构、生成目录、生成章节、章节定稿、批量生成
- **小说编辑模块**：架构编辑、目录编辑、章节编辑、项目资产管理
- **短剧改编模块**：生成改编计划、按计划生成分集脚本、分镜预览、导出
- **任务系统**：创建任务、查询进度、取消任务、重试任务
- **配置中心**：模型配置读取、连通性测试、默认模型管理

### 8.2 前端模块

- **全局页面**：登录/注册、项目列表页、配置中心
- **项目内工作台**：
  - 项目概览
  - 架构页
  - 目录页
  - 章节页
  - 角色/摘要页
  - 短剧改编页
  - 任务监控页

---

## 9. 数据模型设计（MVP 简化版）

### 9.1 核心表

#### users

- id
- username
- email
- hashed_password
- created_at

#### projects

- id
- name
- topic
- genre
- num_chapters
- word_number
- owner_id
- status
- created_at
- updated_at

#### project_members

- id
- project_id
- user_id
- role (admin/editor/viewer)
- joined_at

#### chapters

- id
- project_id
- chapter_num
- title
- outline
- draft
- finalized_text
- status
- version
- updated_at

#### generation_tasks

- id
- project_id
- task_type
- status
- progress
- result_json
- error_msg
- created_by
- created_at
- updated_at

#### drama_projects

- id
- source_project_id
- name
- episode_duration
- max_scenes
- status
- created_at

#### drama_episodes

- id
- drama_project_id
- episode_num
- outline_json
- status
- created_at

#### drama_scripts

- id
- episode_id
- scene_num
- shot_num
- type
- duration
- visual
- action
- dialogue
- camera_movement
- audio

#### project_assets

用于存储半结构化项目资产，避免 MVP 阶段表过度拆分。

字段：

- id
- project_id
- asset_type
- content_text
- content_json
- version
- updated_by
- updated_at

asset_type 可取：

- architecture
- directory
- character_state
- global_summary
- world_rule
- adaptation_plan

---

## 10. 旧项目复用策略

**原则**：复用核心逻辑，不复用旧项目形态。

### 可复用内容

**来自 AI_NovelGenerator**

- llm_adapters.py
- embedding_adapters.py
- novel_generator/architecture.py
- novel_generator/blueprint.py
- novel_generator/chapter.py
- novel_generator/finalization.py
- Prompt 模板
- 部分 memory / vectorstore 逻辑

**来自 novel_to_drama**

- data_loader.py
- episode_mapper.py
- script_generator.py
- exporter.py
- drama prompts

### 必须改造的内容

- 文件读写改为数据库读写
- CLI 参数输入改为 API 输入
- 本地路径依赖改为项目级资源管理
- GUI / 命令行入口不直接复用
- 长耗时调用改为异步任务

---

## 11. API 设计（MVP）

### 11.1 认证

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### 11.2 项目

- `GET /projects`
- `POST /projects`
- `GET /projects/{id}`
- `PUT /projects/{id}`
- `DELETE /projects/{id}`

### 11.3 小说生成

- `POST /projects/{id}/generate/architecture`
- `POST /projects/{id}/generate/directory`
- `POST /projects/{id}/generate/chapter/{num}`
- `POST /projects/{id}/finalize/chapter/{num}`
- `POST /projects/{id}/generate/batch`

### 11.4 内容编辑

- `GET /projects/{id}/assets/{type}`
- `PUT /projects/{id}/assets/{type}`
- `GET /projects/{id}/chapters/{num}`
- `PUT /projects/{id}/chapters/{num}`

### 11.5 短剧改编

- `POST /projects/{id}/drama/plan`
- `GET /projects/{id}/drama/plan`
- `PUT /projects/{id}/drama/plan`
- `POST /projects/{id}/drama/convert`
- `GET /drama/{drama_id}/episodes`
- `GET /drama/episodes/{ep_id}/script`
- `GET /drama/episodes/{ep_id}/export?format=json|csv|md`

### 11.6 任务

- `GET /tasks/{task_id}`
- `POST /tasks/{task_id}/cancel`
- `POST /tasks/{task_id}/retry`

### 11.7 快照（Phase2）

- `POST /projects/{id}/snapshots`
- `GET /projects/{id}/snapshots`
- `POST /projects/{id}/snapshots/{snapshot_id}/restore`

---

## 12. 页面规划

### 12.1 登录页

- 注册 / 登录
- 基础错误提示

### 12.2 项目列表页

- 项目卡片列表
- 创建项目
- 搜索 / 筛选（可后置）

### 12.3 项目工作台

工作台标签页：

- 概览
- 架构
- 目录
- 章节
- 角色/摘要
- 短剧改编
- 任务监控

### 12.4 配置中心

- 模型服务配置
- 模型连通性测试
- 默认模型选择

---

## 13. 路线图

### Phase 1：MVP（单人闭环）

**目标**：一个用户可完成从项目创建到小说生成，再到短剧脚本导出的闭环。

**包含**：

- 项目脚手架
- 登录认证
- 项目 CRUD
- 小说生成流程
- 章节编辑
- 任务异步化
- 改编计划
- 短剧脚本生成
- 导出
- 本地与云端部署跑通

**不包含**：

- 团队协作
- WebSocket
- 编辑锁
- 高级记忆
- 一致性 Agent

### Phase 2：小团队协作

**目标**：支持 2-4 人团队协同使用。

**包含**：

- 成员邀请
- 角色权限
- 编辑锁 / 乐观锁
- 快照恢复
- 更丰富的任务日志
- API 配置中心

### Phase 3：增强智能

**目标**：提高内容质量与系统可维护性。

**包含**：

- 一致性检查
- 全文搜索
- 语义搜索
- 结构化记忆可视化
- 更强的导出与审核能力

---

## 14. 风险与应对

### 风险 1：旧代码与文件系统耦合严重

**应对**：

- 先抽服务层
- 文件逻辑逐步替换成数据库逻辑

### 风险 2：AI 长耗时任务导致请求超时

**应对**：

- 所有生成类任务一律异步化

### 风险 3：需求迭代导致代码越来越乱

**应对**：

- 严格执行：存档 → PRD → Plan → 开发 → Changelog

### 风险 4：AI 乱改多个文件导致不可追溯

**应对**：

- 小步提交
- 每次改动后查看 diff
- 大改前新建分支

### 风险 5：向量存储未来难扩展

**应对**：

- 做抽象层
- MVP 先用 Chroma，后续可迁 Qdrant

---

## 15. 成功标准（MVP 验收）

MVP 完成时必须满足：

1. 用户可以登录
2. 用户可以创建项目
3. 用户可以生成小说架构
4. 用户可以生成目录
5. 用户可以生成至少一章正文
6. 用户可以编辑并保存章节
7. 用户可以生成短剧改编计划
8. 用户可以生成至少一集短剧脚本
9. 用户可以导出脚本
10. 项目可以在云端成功部署并访问
