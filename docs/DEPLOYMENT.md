# 部署指南

## 方案对比

| 方案 | 费用 | 难度 | 推荐度 |
|------|------|------|--------|
| **VPS 自托管** | ~¥5-10/月 | 中等 | **首推**（国内访问快、稳定、不沉睡） |
| **Render + Vercel** | 免费（有限制） | 简单 | 免费但会休眠、国内访问可能慢 |
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
| `ARC_SIZE` | `15` | arc 章节数（每 N 章冻结一次 arc 摘要），可省略，默认 15 |

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

## 方案二：VPS 自托管（首推，~¥5-10/月）

适合长期使用，5-10 人用绰绰有余。国内访问建议选**香港/新加坡节点**（免 ICP 备案，即买即用）。

### 推荐 VPS

| 平台 | 价格 | 配置 | 链接 |
|------|------|------|------|
| 阿里云轻量（香港） | ~¥50/年 | 2GB内存/2核/50GB | aliyun.com |
| 腾讯云轻量（香港） | ~¥50/年 | 2GB内存/2核/50GB | cloud.tencent.com |
| DigitalOcean | $5/月 | 1GB内存/1核/25GB SSD | digitalocean.com |
| Vultr | $5/月 | 1GB内存/1核/25GB SSD | vultr.com |

### 架构

单台 VPS 一键部署全栈：Nginx(:80) 托管前端静态资源 + 反代 `/api` 到后端，后端容器启动时自动执行数据库迁移并同时拉起 uvicorn + Celery worker。

```
用户 → http://VPS_IP:80
  ├── /        → 前端静态资源（Nginx）
  └── /api/*   → 后端 :8000（Nginx 同源反代，免 CORS）
```

### 部署步骤

```bash
# 1. SSH 登录你的 VPS
ssh root@你的服务器IP

# 2. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 3. 安装 docker-compose 插件
apt-get update && apt-get install -y docker-compose-plugin

# 4. 克隆代码
git clone https://github.com/yxx-789/novel_drama.git
cd novel_drama

# 5. 配置生产环境变量（.env 已被 gitignore，不会提交）
cp .env.production.example .env
# 编辑 .env，填入 JWT_SECRET、FERNET_SECRET、LLM_API_KEY（你的 DeepSeek Key）
# 可选：ARC_SIZE（arc 章节数，默认 15，模板已含）

# 6. 启动生产全栈（Nginx + PostgreSQL + Redis + 后端 + Worker）
docker compose -f docker-compose.prod.yml up -d --build

# 7. 验证
curl -s http://localhost/ | grep -o "<title>.*</title>"   # 前端页面
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost/api/auth/login -H "Content-Type: application/json" -d '{"username":"x","password":"y"}'   # 401=API 通了
```

### 访问与可选配置

- 访问 `http://你的服务器IP` 即可使用
- 防火墙/安全组放行 **80 端口**
- 可选：绑定域名 + HTTPS（Nginx 配置证书或套 Cloudflare CDN）

### 重要：DeepSeek API Key 共享计费

- 生产环境的 `LLM_API_KEY` 是**平台默认 Key**：所有没填自己 Key 的用户都会消耗它的余额
- 建议引导用户：进入「AI 模型配置」填写自己的 Key（已加密存储），你的 Key 只作兜底
- 如需完全不让别人用你的 Key，把 `.env` 里的 `LLM_API_KEY` 留空即可强制用户自带

### Docker Hub 访问问题（国内常见）

中国内地/部分网络拉取 Docker Hub 镜像会失败。两种解决办法：

1. **配置镜像加速器**（一劳永逸）：VPS 上新建 `/etc/docker/daemon.json`：
   ```json
   { "registry-mirrors": ["https://docker.m.daocloud.io"] }
   ```
   然后 `systemctl restart docker`
2. **手动拉取后打 tag**（本项目本地验证时即用此法）：
   ```bash
   docker pull docker.m.daocloud.io/library/nginx:alpine && docker tag docker.m.daocloud.io/library/nginx:alpine nginx:alpine
   docker pull docker.m.daocloud.io/library/node:20-alpine && docker tag docker.m.daocloud.io/library/node:20-alpine node:20-alpine
   ```

---

## 方案三：本地电脑 + Cloudflare Tunnel（免费）

如果你有闲置电脑或 NAS：

### 1. 本地启动（生产编排）

```bash
git clone https://github.com/yxx-789/novel_drama.git
cd novel_drama
cp .env.production.example .env   # 填好 JWT_SECRET / FERNET_SECRET / LLM_API_KEY
docker compose -f docker-compose.prod.yml up -d --build
```

### 2. 安装 Cloudflare Tunnel

```bash
# macOS
brew install cloudflared

# 登录
cloudflared tunnel login

# 创建隧道
cloudflared tunnel create novel-drama

# 运行隧道（把本地 80 端口暴露到公网）
cloudflared tunnel run --url http://localhost:80 novel-drama
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
