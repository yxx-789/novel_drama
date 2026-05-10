# 部署指南

## 技术栈

- **后端**: FastAPI + PostgreSQL + Redis + Celery
- **前端**: React + Vite
- **部署平台**: Railway (推荐) 或任意支持 Docker 的平台

---

## 后端部署 (Railway)

### 1. 准备

确保已安装 Railway CLI 并登录：

```bash
npm install -g @railway/cli
railway login
```

### 2. 创建项目

```bash
railway init
```

### 3. 添加服务

在 Railway Dashboard 中：

1. **New Project** → **Deploy from GitHub repo**
2. 选择本仓库
3. Railway 会自动识别 `railway.toml`

### 4. 添加数据库

在 Dashboard 中点击 **New** → **Database** → **Add PostgreSQL**
Railway 会自动注入 `DATABASE_URL` 环境变量。

再添加 **Redis**：**New** → **Database** → **Add Redis**
Railway 会自动注入 `REDIS_URL`。

### 5. 配置环境变量

在 Dashboard → Variables 中添加：

| 变量名 | 说明 | 是否必填 |
|---|---|---|
| `JWT_SECRET` | JWT 签名密钥，建议使用随机字符串 (>=32字符) | ✅ |
| `FERNET_SECRET` | Fernet 加密密钥，用于加密用户 LLM API Key | ✅ |
| `LLM_API_KEY` | 平台默认 LLM API Key (兜底) | 可选 |
| `LLM_BASE_URL` | 平台默认 LLM Base URL | 可选 |
| `LLM_MODEL` | 平台默认模型 | 可选 |
| `CORS_ORIGINS` | 前端域名，多个用逗号分隔 | 可选 |

生成 Fernet 密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 6. 部署

```bash
railway up
```

---

## 前端部署

### 方案 A: Vercel (推荐)

1. 将代码推送到 GitHub
2. 在 [Vercel](https://vercel.com) 导入项目
3. 设置构建命令：`npm run build`
4. 设置输出目录：`dist`
5. 添加环境变量：`VITE_API_URL=https://your-api.railway.app`

### 方案 B: 静态托管

```bash
cd frontend
npm ci
VITE_API_URL=https://your-api.railway.app npm run build
```

将 `dist/` 目录内容上传到任意静态托管服务 (Cloudflare Pages, Netlify, 对象存储等)。

---

## 本地 Docker Compose 部署

```bash
# 复制环境变量模板
cp backend/.env.example backend/.env
# 编辑 .env 填入实际值

# 启动所有服务
docker-compose up --build -d

# 执行数据库迁移
docker-compose exec backend alembic upgrade head
```

---

## 验证

部署完成后检查以下端点：

- `GET /health` → 返回服务状态
- `GET /api/auth/me` → 需要登录，验证 JWT 配置
- 创建项目并测试生成流程

---

## 常见问题

### 数据库迁移失败

如果 Railway 部署时报 Alembic 错误，确保 PostgreSQL 服务已就绪后重新部署。

### CORS 错误

检查 `CORS_ORIGINS` 是否包含前端实际域名（含协议，如 `https://app.vercel.app`）。

### Worker 未启动

Celery worker 需要单独启动。开发环境：

```bash
cd backend
celery -A app.worker.tasks worker --loglevel=info --pool=solo
```

生产环境（Railway）建议作为独立服务部署，或使用 Docker Compose 同时启动 backend 和 worker。

---

## 生产环境检查清单

- [ ] `JWT_SECRET` 已更换为随机强密钥
- [ ] `FERNET_SECRET` 已生成并配置
- [ ] PostgreSQL 和 Redis 已连接
- [ ] `CORS_ORIGINS` 已限制为实际前端域名
- [ ] 健康检查端点 `/health` 可访问
