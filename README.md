# AI 小说 & 短剧创作工作台

面向 2-4 人小团队的 Web 创作工作台，整合小说生成与短剧改编两大 AI 工作流。

## 功能概览

- **小说创作**：AI 生成架构、目录、章节，支持人工编辑与批量导出
- **章节管理**：左右分栏编辑器，支持单章 AI 重写与批量生成
- **短剧改编**：基于小说章节自动生成短剧分集脚本
- **AI 问答**：项目内嵌 AI 助手，辅助创作决策

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 18 + TypeScript + Tailwind CSS + React Query + Zustand |
| 后端 | FastAPI + SQLAlchemy 2.0 + Alembic |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 任务队列 | 当前为 `asyncio.create_task`（待接入持久化队列） |

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
# 1. 启动数据库、Redis、后端
docker-compose up -d

# 2. 执行数据库迁移
cd backend
alembic upgrade head

# 3. 启动前端（另一个终端）
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 方式二：手动启动

**依赖**：Python 3.12 + Node.js 20 + PostgreSQL 16 + Redis 7

```bash
# 后端
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DATABASE_URL、REDIS_URL、JWT_SECRET、LLM_API_KEY 等

alembic upgrade head
uvicorn app.main:app --reload

# 前端（另一个终端）
cd frontend
npm install
npm run dev
```

## 环境变量

详见 `backend/.env.example` 和 `frontend/.env.example`。

关键变量：
- `DATABASE_URL`：PostgreSQL 连接串
- `REDIS_URL`：Redis 连接串
- `JWT_SECRET`：**必填**，用于 Token 签名（生产环境须使用强随机字符串）
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`：LLM 调用配置

## 项目结构

```
.
├── backend/          FastAPI 后端
│   ├── app/
│   │   ├── core/     配置、安全、常量
│   │   ├── infra/    数据库、Redis 封装
│   │   ├── models/   SQLAlchemy 模型
│   │   ├── routers/  API 路由
│   │   ├── services/ 业务逻辑
│   │   └── generator/ LLM adapter、Prompt 模板
│   └── alembic/      数据库迁移
├── frontend/         React 前端
│   ├── src/
│   │   ├── api/      API 请求封装
│   │   ├── components/ 通用组件
│   │   ├── pages/    页面级组件
│   │   └── store/    全局状态（Zustand）
│   └── package.json
├── docs/             项目文档（PRD、架构、API 规范等）
├── memory-bank/      决策记录与进度跟踪
└── docker-compose.yml
```

## 数据库迁移

```bash
cd backend

# 创建新迁移
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 回滚一级
alembic downgrade -1
```

## 文档索引

- [PRD.md](docs/PRD.md) —— 产品需求与 MVP 范围
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) —— 系统架构设计
- [API_SPEC.md](docs/API_SPEC.md) —— API 接口规范
- [DATA_MODEL.md](docs/DATA_MODEL.md) —— 数据模型定义
- [CHANGELOG.md](docs/CHANGELOG.md) —— 变更日志

## 协作规范

见 [AGENTS.md](AGENTS.md)。
