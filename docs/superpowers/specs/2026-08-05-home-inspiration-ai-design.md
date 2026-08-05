# 主页创作灵感（完整版）+ 主页 AI 助手 设计（V2）

- 日期：2026-08-05
- 状态：设计已批准
- 目标项目：`/Users/yxx/Desktop/novel_drama_v2`

## 背景

当前「创作灵感」只在项目详情页内部，用户必须先建项目才能看到热点。用户希望在**创建项目前**就能浏览热点并基于热点创建项目。同时希望主页有 AI 助手（无项目上下文）。

**关键设计原则（用户明确要求）**：主页灵感**不缩水**——直接复用现有完整的灵感浏览体验（32 分类 chips + 搜索 + 完整列表），不做 Top N 减法。

## 功能 1：主页完整版「创作灵感」

**组件复用**：`InspirationTab.tsx` 的 `projectId` 改为**可选**：

| 模式 | 触发 | 行为 |
|------|------|------|
| **项目模式** | 有 `projectId` | 现状不变：浏览 + 「导入项目」→ `POST /api/projects/{id}/inspiration`；展示已导入灵感 |
| **主页模式** | 无 `projectId` | 浏览完整热点 + 每条「**用它创建项目**」→ 跳转创建页并预填 |

**「用它创建项目」流程**：
1. 点击 → `navigate('/projects/create?topic=<标题>&summary=<摘要>&note_id=<id>&likes=<n>&author=<作者>&url=<链接>')`
2. `ProjectCreate.tsx` 读 query 参数预填「名称」（默认=主题）和「主题」
3. 创建成功后：若带 `note_id`，自动 `importInspiration(projectId, note)`（设主题 + 存资产，生成自动参考）
4. 跳转新项目

**布局**：项目列表页（`ProjectList.tsx`）顶部放 `InspirationTab`（主页模式），下方是「我的项目」。

**保留**：项目内「创作灵感」Tab（管理已导入灵感 + 生成时参考）。

## 功能 2：主页 AI 助手（复用 AIChatDrawer）

- `AIChatDrawer.tsx` 的 `projectId` 改**可选**：
  - 有 `projectId` → 项目内行为（项目上下文注入）
  - 无 `projectId` → 通用创作助手（纯 LLM 对话）
- `ProjectList.tsx` header 右上角加「AI 助手」按钮 → 打开 `AIChatDrawer`（无 projectId）
- 后端 `POST /chat-sessions` 已支持 `project_id` 可选；`GET /chat-sessions` 支持无项目过滤。**预期免改后端**，需实测无项目会话发消息正常
- `api/chat.ts` 补充：`listUserChatSessions()`、`createChatSession(projectId?)`

## 全局约束

- 文案中性，**不出现「小红书」字样**
- 不破坏既有功能：项目内 Tab、项目内 AI 助手（带上下文）、创建项目流程回归正常
- 改动后更新 `docs/CHANGELOG.md`（接口不变则 API_SPEC 视情况）
- 前端 `npm run build` 零错误

## 涉及文件

- `frontend/src/pages/ProjectList.tsx` —— 顶部放 InspirationTab（主页模式）+ header 加 AI 助手按钮
- `frontend/src/components/InspirationTab.tsx` —— `projectId` 可选 + 主页模式「用它创建项目」
- `frontend/src/pages/ProjectCreate.tsx` —— 读 query 预填 + 创建后自动导入灵感
- `frontend/src/components/AIChatDrawer.tsx` —— `projectId` 可选 + 通用模式
- `frontend/src/api/chat.ts` —— 补充通用会话函数
- `backend/app/services/chat_service.py` —— 仅验证无项目上下文正常（预期无改动）
- `docs/CHANGELOG.md` —— 记录

## 不在范围

- 主页灵感的分页
- 主页 AI 助手历史会话的深度管理
- VPS 部署
