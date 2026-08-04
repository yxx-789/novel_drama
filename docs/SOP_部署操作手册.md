# AI 小说 & 短剧创作工作台 —— 从零到上线部署 SOP

> 版本：v1.0 ｜ 适用系统：macOS（本地）+ Ubuntu 22.04（服务器）
> 目标：把本项目部署到一台香港 VPS，让其他人通过链接使用。
> 本文档由一次真实部署全程整理而成，所有命令均经过实测。

---

## 目录

1. [项目是什么](#0-项目是什么)
2. [阶段一：本地代码准备（推送到 GitHub）](#阶段一本地代码准备)
3. [阶段二：认识生产部署文件](#阶段二认识生产部署文件)
4. [阶段三：VPS 部署（核心流程）](#阶段三vps-部署核心流程)
5. [踩过的坑与解决方案](#踩过的坑与解决方案)
6. [日常运维](#日常运维)
7. [安全清单](#安全清单)

---

## 0. 项目是什么

面向 2-4 人小团队的 AI 创作工作台：**小说生成**（架构/目录/章节）+ **短剧改编**（分集脚本）+ **AI 问答**。

- 前端：React + Vite（构建后由 Nginx 托管）
- 后端：FastAPI + SQLAlchemy（Docker 容器）
- 存储：PostgreSQL + Redis
- 异步：Celery worker
- AI：DeepSeek API（`deepseek-chat`）

**部署架构**（单台 VPS 全搞定）：

```
用户 → http://服务器IP:80
  ├── /        → 前端静态资源（Nginx）
  └── /api/*   → 后端 :8000（Nginx 同源反代，免 CORS）
```

---

## 阶段一：本地代码准备

### 1.1 首次提交并推送

项目首次部署前，代码必须先推到 GitHub。**注意：仓库名必须是存在的**（本 SOP 以 `yxx-789/novel_drama` 为例）。

```bash
cd /你的项目路径/novel_drama
git checkout -b main
git add -A
git commit -m "Initial commit"
git push -u origin main
```

> ⚠️ **分支名不能以 `.` 开头**。如果遇到 `分支名无效` 或 `cannot lock ref 'HEAD'` 的错误，说明分支名是非法的（如 `.invalid`），用以下命令修复：
>
> ```bash
> git symbolic-ref HEAD refs/heads/main
> rm -f .git/refs/heads/.invalid
> git commit -m "Initial commit"
> ```

### 1.2 GitHub 认证

GitHub **不再支持账号密码**做 git 操作，必须用 Token 或 gh CLI。

**方式 A：Personal Access Token**
1. 打开 `https://github.com/settings/tokens` → Generate new token → 勾选 `repo`
2. 推送时在 Password 提示处**粘贴 Token**（不是密码）

**方式 B：gh CLI（推荐，最稳）**
```bash
gh auth login        # 选 GitHub.com → HTTPS → Login with a web browser → 浏览器授权
gh auth setup-git
git push -u origin main
```

### 1.3 修改 GitHub 默认分支（建议）

1. 打开 `https://github.com/yxx-789/novel_drama/settings/branches`
2. 「Default branch」→ 铅笔图标 → 选 `main` → Update

> 不设置也行，但克隆时必须带 `-b main`，否则会克隆到旧分支。

---

## 阶段二：认识生产部署文件

仓库里负责生产部署的 4 个文件：

| 文件 | 作用 |
|------|------|
| `docker-compose.prod.yml` | 生产编排：Nginx(:80) + PostgreSQL + Redis + 后端 + Worker |
| `frontend/Dockerfile` | 前端多阶段构建：React 打包 → Nginx 托管 |
| `frontend/nginx.conf` | 静态资源 + `/api` 反向代理到后端（同源免 CORS） |
| `.env.production.example` | 生产环境变量模板（复制为 `.env` 后填写） |

> 后端生产镜像用的是已有的 `backend/Dockerfile`（多阶段构建 + supervisord 同时拉起 uvicorn 和 celery）。

---

## 阶段三：VPS 部署（核心流程）

### 步骤 1：购买 VPS

| 平台 | 推荐配置 | 价格 |
|------|---------|------|
| 腾讯云轻量（香港） | 2GB 内存 / 2核 / 50GB | ~¥50/年 |
| 阿里云轻量（香港） | 2GB 内存 / 2核 / 50GB | ~¥50/年 |
| DigitalOcean | 1GB 内存 / 1核 | $5/月 |

**系统镜像选 Ubuntu 22.04（64 位）**。选**香港/新加坡节点**（免备案、Docker Hub 直连）。

### 步骤 2：SSH 登录

```bash
ssh root@你的服务器IP
```

- 首次问 `Are you sure...` → 输 `yes`
- 输 root 密码（屏幕不显示，正常）
- 看到 `root@xxx:~#` 即成功

> 如果提示 `Connection closed`（密码被拒），到云控制台「重置密码」→ 重启实例 → 重试；或用控制台的「远程连接」网页方式登录。

### 步骤 3：安装 Docker

```bash
curl -fsSL https://get.docker.com | sh
```

验证（compose 插件会随脚本装好）：

```bash
docker --version
docker compose version
```

测试拉镜像（香港节点一般直连成功）：

```bash
docker pull hello-world
```

### 步骤 4：克隆代码

```bash
cd /root
git clone -b main https://github.com/yxx-789/novel_drama.git
cd novel_drama
```

> 一定要 `-b main`。确认部署文件在：`ls docker-compose.prod.yml frontend/Dockerfile`

### 步骤 5：配置环境变量

```bash
cp .env.production.example .env
```

生成两个密钥（各复制输出）：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
python3 -c "import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

编辑 `.env`：

```bash
nano .env
```

填这三行（其余保持默认）：

```
JWT_SECRET=<第一个命令的输出>
FERNET_SECRET=<第二个命令的输出>
LLM_API_KEY=sk-你的DeepSeekKey
```

保存：`Ctrl+O` → 回车 → `Ctrl+X`。

### 步骤 6：启动（首次约 5-10 分钟）

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

**首次会构建两个镜像**（后端 pip 装依赖 + 前端 npm 打包），这期间屏幕进度条不滚动是**正常的**，别中途 Ctrl+C。

> 看到 `debconf: falling back to frontend: Noninteractive` 是 apt 的正常提示，不是错误。

成功标志：看到 5 个容器 `Started`。

### 步骤 7：验证

```bash
docker compose -f docker-compose.prod.yml ps          # 5 个都是 Up
curl -s http://localhost/ | grep -o "<title>.*</title>"   # 输出前端标题
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost/api/auth/login -H "Content-Type: application/json" -d '{"username":"x","password":"y"}'
# 输出 401 = API 通
```

### 步骤 8：放行 80 端口（关键，容易漏）

云控制台 → 轻量应用服务器 → 你的实例 → **防火墙** → **添加规则**：
- 端口：`80`
- 协议：`TCP`
- 允许：`0.0.0.0/0`

### 步骤 9：浏览器验证 + 上线

打开 `http://你的服务器IP` → 看到登录页即部署成功，可以分享链接了。

---

## 踩过的坑与解决方案

| 问题 | 现象 | 解决 |
|------|------|------|
| **Docker Hub 拉不到镜像** | `docker pull` 报 `EOF` / `timeout` | 配置镜像加速器：`/etc/docker/daemon.json` 写 `{"registry-mirrors":["https://docker.m.daocloud.io"]}`，重启 docker |
| **compose 构建后卡死** | 镜像已构建（`docker images` 能看到），但容器没创建，进程挂着不动 | `Ctrl+C` 停掉，改用**不带 `--build`** 的命令：`docker compose -f docker-compose.prod.yml up -d`（镜像已存在，秒起） |
| **pip 装依赖时看着没进度** | 构建屏幕长时间停在某一步 | 正常。用另一个终端 `ps aux | grep pip` 确认进程在跑 |
| **SSH 连接中断** | `Connection closed` / `Broken pipe` | 重连即可；若卡死的 compose 进程还在，`kill <PID>` 清理后重新 `up -d` |
| **克隆到旧分支** | 页面没有部署文件 | 克隆带 `-b main`，或把 GitHub 默认分支改成 main |
| **GitHub 推送鉴权失败** | `Password authentication is not supported` | 用 Token 或 `gh auth login`（见 1.2） |
| **前端 404 / 白屏（深链接）** | 刷新 `/projects` 等路由报 404 | 检查 nginx.conf 是否有 `try_files $uri $uri/ /index.html;`（已内置） |

---

## 日常运维

### 更新代码（发布新版本）

```bash
cd /root/novel_drama
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### 查看日志

```bash
# 后端日志（含 AI 生成过程）
docker compose -f docker-compose.prod.yml logs -f backend

# Worker 日志（AI 任务执行）
docker compose -f docker-compose.prod.yml logs -f worker

# 全部日志
docker compose -f docker-compose.prod.yml logs -f
```

### 重启 / 停止

```bash
docker compose -f docker-compose.prod.yml restart    # 全部重启
docker compose -f docker-compose.prod.yml down       # 停止（数据保留在 volume）
```

### 备份数据库

```bash
docker exec ai-novel-studio-prod-db pg_dump -U postgres ai_novel_studio > backup.sql
```

### 管理 DeepSeek Key（省钱要点）

- 平台默认 Key（`.env` 里的 `LLM_API_KEY`）会被所有没填自己 Key 的用户消耗
- 引导用户：进「AI 模型配置」填自己的 Key（已加密存储）
- 想完全不让别人用你的 Key → `.env` 里 `LLM_API_KEY` 留空

---

## 安全清单

- [ ] `JWT_SECRET` 是强随机串（不要用开发环境的默认值）
- [ ] `FERNET_SECRET` 已生成
- [ ] 阿里云防火墙只放行必要端口（80；如需 SSH 才放 22）
- [ ] GitHub Token 用完定期轮换（`github.com/settings/tokens` 重新生成）
- [ ] 给 VPS 定期 `apt update && apt upgrade -y`
- [ ] 数据库定期备份（见上）

---

## 附：环境变量说明（.env）

| 变量 | 必填 | 说明 |
|------|------|------|
| `JWT_SECRET` | ✅ | 登录 Token 签名密钥，必须强随机 |
| `FERNET_SECRET` | ✅ | 加密用户自填 API Key，必须生成 |
| `LLM_API_KEY` | 看策略 | 平台默认 DeepSeek Key（留空=强制用户自带） |
| `LLM_BASE_URL` | 否 | 默认 `https://api.deepseek.com` |
| `LLM_MODEL` | 否 | 默认 `deepseek-chat`（不要用推理模型，会空输出卡死） |
| `LLM_MAX_TOKENS` | 否 | 默认 `8192`（2048 会截断章节草稿） |
| `CORS_ORIGINS` | 否 | 同源部署不用改 |

> ⚠️ **模型坑**：`deepseek-v4-flash` 是推理模型，会把 token 全耗在思考上、返回空内容导致任务卡死。务必用 `deepseek-chat`。
