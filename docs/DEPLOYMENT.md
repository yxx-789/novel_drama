# 部署指南

## 方案对比

| 方案 | 费用 | 难度 | 推荐度 |
|------|------|------|--------|
| **Render + Vercel** | 免费（有限制） | 简单 | 首推 |
| **VPS 自托管** | ~$5/月 | 中等 | 最稳定 |
| **本地服务器 + Cloudflare Tunnel** | 免费 | 中等 | 有闲置设备时 |

---

## 方案一：Render + Vercel（免费，有休眠限制）

Render 提供免费的 Web Service 和 PostgreSQL（90 天有效期）。Vercel 免费托管前端。

> 限制：Render 免费实例 15 分钟无访问会自动休眠，下次访问需等待 30 秒唤醒。

### 1. 注册账号

1. 打开 https://render.com
2. 点击 **"Get Started for Free"**
3. 用 **GitHub** 账号登录

### 2. 部署后端（Web Service）

1. 登录 Render Dashboard 后，点击 **"New +"** → **"Web Service"**
2. 在 GitHub 仓库列表中找到 **"yxx-789/novel_drama"**
3. 点击 **"Connect"**

配置构建：

| 配置项 | 值 |
|--------|-----|
| **Name** | `novel-drama-api` |
| **Region** | 选 `Singapore`（离你最近） |
| **Branch** | `feature/p0-optimizations` |
| **Root Directory** | `backend` |
| **Runtime** | `Docker` |
| **Dockerfile Path** | `./Dockerfile` |

点击 **"Create Web Service"**。

### 3. 添加 PostgreSQL 数据库

1. 点击左侧 **"New +"** → **"PostgreSQL"**
2. Name 填：`novel-drama-db`
3. Region 选和上面一样的 `Singapore`
4. 点击 **"Create Database"**

创建完成后，点击数据库卡片 → **"Connections"** 标签，复制 **"Internal Database URL"**。

### 4. 配置环境变量

回到你的 Web Service，点击 **"Environment"** 标签，添加：

| 变量名 | 值 | 获取方式 |
|--------|-----|---------|
| `DATABASE_URL` | 粘贴 Internal Database URL | 上一步复制的 |
| `REDIS_URL` | 见下方 | Redis Cloud 免费套餐 |
| `JWT_SECRET` | 随机字符串 | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `FERNET_SECRET` | Fernet 密钥 | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `CORS_ORIGINS` | 先填 `*` | 部署完前端再改成 Vercel 地址 |

**Redis 获取方式（免费）：**

1. 打开 https://redis.io/try-free/
2. 注册账号
3. 创建免费数据库（30MB 够用了）
4. 在 **"Configuration"** 里找到连接串，格式类似：
   ```
   redis://default:密码@主机:端口
   ```
5. 把这个连接串填到 `REDIS_URL`

### 5. 重新部署

添加环境变量后，Render 会自动重新部署。等状态变成绿色 **"Live"**。

### 6. 获取后端域名

在 Web Service 页面顶部，看到类似：
```
https://novel-drama-api.onrender.com
```
**复制保存**，后面前端要用。

验证：浏览器访问 `https://你的域名/health`，返回 `{"status":"ok"}` 即成功。

---

### 7. 部署前端到 Vercel

1. 打开 https://vercel.com，用 GitHub 登录
2. 点击 **"Add New..."** → **"Project"**
3. 导入 `yxx-789/novel_drama`

配置：

| 配置项 | 值 |
|--------|-----|
| **Framework Preset** | `Vite` |
| **Root Directory** | `frontend` |
| **Build Command** | `npm run build` |
| **Output Directory** | `dist` |

在 **Environment Variables** 里添加：

```
VITE_API_URL=https://novel-drama-api.onrender.com
```

（换成你实际的后端地址）

点击 **"Deploy"**。

### 8. 打通 CORS

等 Vercel 部署完成，获得前端域名（如 `https://novel-drama.vercel.app`）。

回到 Render → Web Service → Environment，把 `CORS_ORIGINS` 从 `*` 改成：
```
https://novel-drama.vercel.app
```

Render 会自动重新部署。

---

## 方案二：VPS 自托管（$5/月，最稳定）

适合长期使用，5-10 人用绰绰有余。

### 推荐 VPS

| 平台 | 价格 | 配置 | 链接 |
|------|------|------|------|
| DigitalOcean | $5/月 | 1GB内存/1核/25GB SSD | digitalocean.com |
| Vultr | $5/月 | 1GB内存/1核/25GB SSD | vultr.com |
| 阿里云轻量 | ~¥60/年 | 2GB内存/1核/50GB | aliyun.com |
| 腾讯云轻量 | ~¥50/年 | 2GB内存/1核/50GB | cloud.tencent.com |

### 部署步骤

```bash
# 1. SSH 登录你的 VPS
ssh root@你的服务器IP

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 3. 安装 docker-compose
apt-get update && apt-get install -y docker-compose-plugin

# 4. 克隆代码
git clone https://github.com/yxx-789/novel_drama.git
cd novel_drama

# 5. 复制环境变量
cp backend/.env.example backend/.env
# 编辑 .env，填入实际的 DATABASE_URL、REDIS_URL、JWT_SECRET、FERNET_SECRET

# 6. 启动所有服务（PostgreSQL + Redis + 后端 + Worker）
docker-compose up --build -d

# 7. 执行数据库迁移
docker-compose exec backend alembic upgrade head
```

后端就跑在 `http://你的服务器IP:8000`。

前端部署到 Vercel（免费），`VITE_API_URL` 填你的服务器 IP。

---

## 方案三：本地电脑 + Cloudflare Tunnel（免费）

如果你有闲置电脑或 NAS：

### 1. 本地启动

```bash
cd /Users/xingyao/Desktop/小说图像生成_轻量版
docker-compose up -d
cd backend && alembic upgrade head
```

### 2. 安装 Cloudflare Tunnel

```bash
# macOS
brew install cloudflared

# 登录
cloudflared tunnel login

# 创建隧道
cloudflared tunnel create novel-drama

# 运行隧道（把本地 8000 端口暴露到公网）
cloudflared tunnel run --url http://localhost:8000 novel-drama
```

会得到一个 `https://xxx.trycloudflare.com` 的公网地址。

### 3. 前端部署

Vercel 的 `VITE_API_URL` 填 Cloudflare 隧道地址。

---

## 生产环境检查清单

- [ ] `JWT_SECRET` 已更换为随机强密钥
- [ ] `FERNET_SECRET` 已生成并配置
- [ ] PostgreSQL 和 Redis 已连接
- [ ] `CORS_ORIGINS` 已限制为实际前端域名
- [ ] `/health` 端点可访问
- [ ] Celery Worker 正常运行（生成任务不卡在 0%）

## 常见问题

**Q: Render 免费实例休眠后，第一次访问很慢？**
A: 正常。15 分钟无访问会自动休眠，下次访问需等待 30 秒唤醒。可以写个定时脚本每 10 分钟 ping 一次 `/health` 保持活跃。

**Q: 为什么生成架构卡在 0%？**
A: Worker 没启动。检查 Render Logs 里是否有 Celery 启动日志。如果用 Docker Compose，检查 `worker` 容器是否正常运行。

**Q: Render PostgreSQL 90 天后怎么办？**
A: 免费数据库 90 天后会被删除。到期前导出数据，重新创建数据库并导入。或者改用 Supabase（免费 PostgreSQL，永久有效）。

**Q: 前端提示 "网络错误"？**
A: CORS 没配好。检查后端 `CORS_ORIGINS` 是否等于前端域名（含 `https://`）。
