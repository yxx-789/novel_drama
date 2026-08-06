# HANDOFF — 项目交接与恢复指南

> **生成时间**：2026-08-06（本次会话末）
> **用途**：重启电脑 / 新开终端后，无缝衔接本项目。新 Claude Code 会话请先读本文件。
> **一句话**：代码已完成并推上 GitHub，服务器已部署好，**唯一没做完的事是往服务器库导入 486 条热点数据**（见 §4.1）。

---

## 1. 项目位置与当前状态

| 项 | 值 |
|---|---|
| 项目路径 | `/Users/yxx/novel_drama_v2`（**注意：已从桌面搬到这**，桌面路径已失效） |
| 当前分支 | `feature/v3-p2-memory`（已推 GitHub `origin/feature/v3-p2-memory`） |
| 主干 `main` | 已 fast-forward 合并全部工作并推 GitHub `origin/main` |
| 最新提交 | `7020ebc fix: 变更历史字段名不匹配…` |
| GitHub 仓库 | `https://github.com/yxx-789/novel_drama` |
| 测试 | 全量 **330 passed**（`cd backend && source .venv/bin/activate && python -m pytest app/tests/ -q`） |
| 服务器 | `8.221.116.98`（实例 `993eab91f17c44ec9aabd49412f8e521`，Ubuntu 22.04），**已部署最新版** |

---

## 2. 本次会话做的事

### 2.1 代码改动（已提交，均有回归测试）

1. **短剧大纲 JSON 解析失败修复**（Bug 1）
   - 根因：DeepSeek 偶发输出退化（只有 `json` 围栏）或含未转义英文引号的畸形 JSON
   - 修复：`backend/app/generator/llm_utils.py` 新增 `repair_stray_quotes`（全角引号修复）+ `_parse_llm_json` 兜底候选 + 解析失败重试循环；退化输出视为空触发重试

2. **「角色与世界」世界设定纵向逐字显示修复**（Bug 2）
   - 根因：`world` 段是扁平结构（`{current_date: "…", location: "…"}`），前端 `Section` 按两层嵌套遍历 `Object.entries(字符串)` 把字符串逐字拆开
   - 修复：`frontend/src/pages/ProjectDetail/WorldStateTab.tsx` 兼容嵌套/扁平两种 shape

3. **短剧脚本导出 500 + 批量导出越权**（Bug 3）
   - 根因：asyncpg 返回 `pgproto.UUID`（有 `__str__` 无 `.replace`），`uuid.UUID(pgproto_UUID)` 抛 AttributeError
   - 修复：`backend/app/routers/drama.py` 三处改 `uuid.UUID(str(...))`；批量导出加越权防护（同项目 + 归属校验）

4. **变更历史全显示 `- → -`**（Bug 4，本次最后）
   - 根因：后端写 `{entity, from, to}`，前端读 `key/old/new`，全读不到
   - 修复：`WorldStateTab.tsx` 改读 `entity/from/to`，world 类冗余 entity 省略，数组值用 `、` 拼接

### 2.2 GitHub 上传

- 本地 `main`（47 commits）+ `feature/v3-p2-memory`（28 commits）全部推送到 `origin`
- 远端现在是完整项目（230 个源文件）。**数据/密钥不在 GitHub**：`.env`（gitignore）、Postgres 数据、`node_modules`、`.venv` 都不在。

### 2.3 服务器部署（教你的操作 + 踩坑）

服务器 `8.221.116.98` 走生产编排 `docker-compose.prod.yml`（Nginx:80 + 后端 + worker + db + redis），5 个容器全部运行中，数据库迁移已自动执行。

**这次踩的最大的坑**：服务器实际只有 **890MB 内存**（不是文档说的 2GB），无 swap，并行构建时 OOM → 服务器冻结、SSH 超时/断连、反复卡死。已解决，方案见 §6。

---

## 3. 当前运行状态（重启前快照）

### 3.1 本地（Mac）

| 服务 | 状态 |
|---|---|
| 前端 Vite（localhost:5173） | **已停止**（本次主动停的） |
| 后端容器 `ai-novel-studio-backend` | **已停止** |
| worker 容器 `ai-novel-studio-worker` | **已停止** |
| `ai-novel-studio-db`（PostgreSQL） | 运行中（数据都在，含 486 条热点） |
| `ai-novel-studio-redis` | 运行中 |

### 3.2 服务器

| 服务 | 状态 |
|---|---|
| `ai-novel-studio-prod-web`（Nginx :80） | 运行中 |
| `ai-novel-studio-prod-backend` | 运行中（迁移已跑：`add actual_summary_json`） |
| `ai-novel-studio-prod-worker` | 运行中（celery ready） |
| `ai-novel-studio-prod-db` / `-redis` | 运行中 |
| `hot_topics` 表 | **空（待导入 486 条）** |

---

## 4. 重启后的待办

### 4.1 ⭐ 唯一挂起任务：往服务器导入 486 条热点数据

`/Users/yxx/hot_topics_dump.sql`（486 条，纯 INSERT，已生成好）还没传。

**第 1 步（Mac 新终端）**，传文件（提示输服务器密码）：
```bash
scp /Users/yxx/hot_topics_dump.sql root@8.221.116.98:/root/
```

**第 2 步（服务器终端）**，导入并验证：
```bash
docker exec -i ai-novel-studio-prod-db psql -U postgres -d ai_novel_studio < /root/hot_topics_dump.sql
docker exec ai-novel-studio-prod-db psql -U postgres -d ai_novel_studio -t -A -c "SELECT count(*) FROM hot_topics;"
```
期望输出 **486**。然后刷新 `http://8.221.116.98` 的「创作灵感」页即可看到数据。

> 数据来源：本地开发库之前 launchd 采集器积累的小红书热点。以后想让服务器灵感区持续更新，需把采集器配到服务器上（可选，不急）。

### 4.2 启动本地开发环境（如果想继续本地开发）

```bash
cd /Users/yxx/novel_drama_v2
docker compose up -d          # 拉起 backend + worker（db/redis 已在跑）
cd frontend && npm run dev    # 前端 http://localhost:5173，/api 由 Vite 代理到 :8000
```

⚠️ 改了后端代码后：**Celery worker 不会自动重载**（uvicorn 会 reload，worker 不会），需 `docker compose restart worker`。

### 4.3 服务器使用检查清单

- 浏览器访问 `http://8.221.116.98`，用已有账号登录或注册
- 生成小说/短剧前，确认后台「AI 模型配置」里填了自己的 DeepSeek Key（服务器 `.env` 的 `LLM_API_KEY` 若为空，生成会报错）

---

## 5. 关键命令速查

### 服务器
```bash
ssh root@8.221.116.98
cd /root/novel_drama
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build    # 小改动可去掉 --build
docker compose -f docker-compose.prod.yml ps               # 看 5 个容器
docker logs --tail 50 ai-novel-studio-prod-backend         # 后端日志
```

### 本地
```bash
# 启动
docker compose up -d
cd frontend && npm run dev
# 测试
cd backend && source .venv/bin/activate && python -m pytest app/tests/ -q
# 前端类型检查
cd frontend && npx tsc --noEmit
```

### 提交/推送
```bash
git add -A && git commit -m "fix: …"
git push origin feature/v3-p2-memory
# 合并回 main：git checkout main && git merge feature/v3-p2-memory && git push origin main
```

---

## 6. 服务器部署经验（这台 890MB 的机器，下次不慌）

1. **必须加 swap**（否则构建 OOM → 服务器冻结 → SSH 超时）：
   ```bash
   if ! swapon --show | grep -q /swapfile; then
     fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
     grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
   fi
   ```
   （服务器上已经建好 2GB swap，重启不影响，fstab 已持久化）
2. **构建前先停旧容器腾内存**：`docker stop $(docker ps -q)`
3. **逐个构建，绝不并行**（并行 web + worker 直接内存爆）：
   ```bash
   docker compose -f docker-compose.prod.yml build backend
   docker compose -f docker-compose.prod.yml build worker
   docker compose -f docker-compose.prod.yml build web
   ```
4. **国内 Docker Hub 慢/卡** → 配镜像加速器（已配好）：
   ```bash
   cat > /etc/docker/daemon.json <<'EOF'
   { "registry-mirrors": ["https://docker.m.daocloud.io"] }
   EOF
   systemctl restart docker
   ```
5. **SSH 老断** → 用 tmux 跑长任务：`tmux new -s deploy` … 断了就 `tmux attach -t deploy`
6. **`web` 那步（tsc+vite）最慢最吃内存**，5~10 分钟正常，看它日志在动就不是卡死
7. **服务器 SSH 卡/超时先判断**：`ping` 通 = 服务器活着；`nc -vz -w 5 IP 22` 通 = 端口 OK；都挂了去阿里云控制台用 Workbench 带外连接 / 重启实例（`pg_data` 卷在，数据不丢）

---

## 7. 项目背景（给新会话/后续开发）

- **技术栈**：FastAPI + SQLAlchemy async + asyncpg + PostgreSQL + Celery（Redis broker）+ React/Vite，Docker Compose。LLM 走 DeepSeek（deepseek-chat），**纯文生文**，无图生视频。
- **容器命名**：本地开发 `ai-novel-studio-*`，生产 `ai-novel-studio-prod-*`
- **迁移**：Alembic，生产后端容器启动时自动 `alembic upgrade head`
- **短剧管线**：大纲（3 章/集 → outline_json）→ 分镜脚本（script_json，含 scenes/shots/visual/action/dialogue/audio）→ 导出 json/md/csv
- **记忆系统（V3 P2/P3）**：L1 单章摘要 / L2 arc 摘要 / L3 全书摘要 + 伏笔台账（foreshadowing 资产，known_by 信息约束）
- **创作灵感**：独立采集器 `scripts/xhs_hot_collector.py`，通过小红书 MCP 服务（`~/Desktop/xhs-get/xiaohongshu-mcp`，localhost:18060）抓热点写 `hot_topics` 表；Mac 上用 launchd 每天 8:30 定时（`scripts/launchd.example.plist`）
- **约定**：`.env` 一律 gitignore 不上传；生成的文案**禁止出现「小红书」**（CLAUDE.md 规则）
- **下一步规划（用户已明确，暂缓）**：独立短剧生产项目（脚本 → 文生图/图生视频/成片），输入契约即 `script_json` 结构
