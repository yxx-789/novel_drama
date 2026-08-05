# 写作配置冲突规则引擎 实施计划（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 给积木式生成加冲突规则引擎——硬冲突禁选/拒绝，软冲突提示确认，覆盖 8 维两两冲突 + 豁免。

**Architecture:** `block_library.py` 定义规则数据 + 检测函数（单一真源）；`project_service` 创建时校验硬冲突；前端实时检测（灰禁 + 软提示）。

**Tech Stack:** Python + SQLAlchemy + React/TypeScript。

## Global Constraints

- 规则数据单一真源 `block_library.py`
- 硬冲突：前端禁选 + 后端拒绝；软冲突：提示不阻断
- 无冲突时行为与现状一致（不破坏创建流程）
- 文案不出现「小红书」；`npm run build` 零错误；后端测试通过
- 更新 `docs/CHANGELOG.md`

---

### Task 1: 后端规则数据 + 检测函数

**Files:**
- Modify: `backend/app/generator/block_library.py`
- Modify: `backend/app/tests/test_block_library.py`

**Interfaces:**
- Produces: `BACKGROUND_SYSTEMS` / `GENRE_HARD_BACKGROUND` / `HARD_CONFLICTS` / `SOFT_WARNINGS` 数据；`check_hard_conflicts(config) -> list[str]` / `check_soft_warnings(config) -> list[str]` / `validate_writing_config(config) -> {hard, soft, valid}`

- [ ] **Step 1: 规则数据**
  - `BACKGROUND_SYSTEMS`（4 系，山野 neutral=True）
  - `GENRE_HARD_BACKGROUND`（历史禁现代/未来；体育禁古风/未来）
  - `HARD_CONFLICTS`（精简×群像；无敌流×打脸；娇软×女强）
  - `SOFT_WARNINGS`（罕见融合/卖点错位/文风×受众张力/文风×题材/结构×受众/规模×题材/结构×背景/重生×穿越冗余/剧情走向×设定 关键词冲突）

- [ ] **Step 2: 检测函数**
  - `check_hard_conflicts`：背景跨系（同维多选）、题材×背景系、规模×结构、卖点互斥
  - `check_soft_warnings`：按 SOFT_WARNINGS 规则匹配，返回提示文本列表；剧情走向用关键词检测（含"现代/都市/星际/末世/古代/宗门"等词 vs 所选背景系）
  - `validate_writing_config`：汇总

- [ ] **Step 3: 测试**——`test_block_library.py` 加：背景跨系硬冲突、历史×现代、精简×群像、无敌×打脸、仙侠×末世软警告、冷峻×轻松软警告、剧情走向冲突、无冲突返回空

- [ ] **Step 4: 测试跑通**——`docker compose exec -T backend python -m pytest app/tests/test_block_library.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/generator/block_library.py backend/app/tests/test_block_library.py
git commit -m "feat: writing config conflict rules engine"
```

---

### Task 2: 后端创建校验

**Files:**
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/tests/`（若有 service 测试）

**Interfaces:**
- Consumes: `validate_writing_config`
- Produces: `create_project` 对硬冲突返回 400（含冲突项）

- [ ] **Step 1: create_project 校验**——调用 `validate_writing_config`，硬冲突非空 → raise HTTPException(400, detail=f"写作配置冲突: {冲突}")（或 ValueError，由 router 转 400）

- [ ] **Step 2: 验证**——有硬冲突的 config 创建被拒；无冲突正常创建

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/project_service.py
git commit -m "feat: reject writing config with hard conflicts on create"
```

---

### Task 3: 前端实时冲突检测

**Files:**
- Modify: `frontend/src/pages/ProjectCreate.tsx`
- Modify: `frontend/src/constants/blocks.ts`（或新建 conflict 规则副本）

**Interfaces:**
- Consumes: 后端规则（前端用常量副本，向后端看齐）
- Produces: 选题材灰禁背景、选背景跨系禁选、选规模禁冲突结构、软冲突弹确认、硬冲突阻止提交

- [ ] **Step 1: 前端规则副本**——BACKGROUND_SYSTEMS/GENRE_HARD_BACKGROUND/HARD_CONFLICTS/SOFT_WARNINGS 的轻量版

- [ ] **Step 2: 创建页联动**
  - 选题材 → 灰掉禁用的背景系（disabled）
  - 选背景 → 同系可选、跨系禁选
  - 选规模 → 冲突结构禁用
  - 软冲突：选中后弹 confirm 提示（"…是否继续？"）
  - 提交前：硬冲突 → 阻止 + 提示

- [ ] **Step 3: 构建**——`cd frontend && npm run build` 零错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProjectCreate.tsx frontend/src/constants/blocks.ts
git commit -m "feat: real-time conflict detection on project create"
```

---

### Task 4: 端到端验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 实测**——创建页：选 历史 → 背景星际/都市灰掉；选 仙侠+末世 → 弹软警告；选 精简+群像 → 结构禁用；提交硬冲突组合 → 被拒

- [ ] **Step 2: 回归**——无冲突创建正常；后端测试 + 前端构建

- [ ] **Step 3: CHANGELOG**——「写作配置冲突规则引擎」小节

- [ ] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record writing config conflict rules"
```

---

## 验收清单

- [ ] 硬冲突：背景跨系 / 历史×现代未来 / 精简×群像 / 无敌×打脸 / 娇软×女强 全部拦截
- [ ] 软警告：罕见融合/错位/张力/剧情走向冲突 提示但不阻断
- [ ] 前端实时灰禁 + 弹确认
- [ ] 后端创建校验（硬冲突 400）
- [ ] 无冲突行为不变；构建零错误；既有功能回归
