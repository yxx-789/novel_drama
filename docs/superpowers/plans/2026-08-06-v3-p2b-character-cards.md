# V3 P2-B 实施计划：角色卡系统 + known_by（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** `characters` 资产从无限增长文本重构为**结构化角色卡**（人设/当前状态/关系/known 认知边界/出场追踪），每章写后 LLM 更新，写前只加载出场角色卡，防止长篇小说角色状态稀释。

**Architecture:** 新 prompt `character_card_update_prompt`；`update_character_cards`（写后更新）+ `load_active_character_cards`（写前加载出场角色卡，从上一章 actual_summary_json.characters 取）；task_service 接入；旧文本 characters 兼容降级。

**Tech Stack:** Python + SQLAlchemy + JSON。

## Global Constraints

- 每章写后 +1 LLM 调用（可接受）
- 旧项目（characters 为文本）兼容：降级原样注入，不崩溃
- 不破坏既有功能（架构/目录/章节/短剧）
- 文案不出现「小红书」；后端测试通过
- 更新 `docs/CHANGELOG.md`

---

### Task 1: 角色卡函数 + prompt

**Files:**
- Modify: `backend/app/generator/prompts.py`（`character_card_update_prompt`）
- Modify: `backend/app/services/generation_service.py`（`update_character_cards` / `load_active_character_cards` / `_render_character_cards`）

**Interfaces:**
- Produces:
  - `update_character_cards(db, project_id, chapter, old_state: str, llm_config) -> dict`（更新角色卡 JSON）
  - `load_active_character_cards(db, project_id, chapter, llm_config) -> str`（只注入出场角色卡文本）
  - `_render_character_cards(characters_json, active_names) -> str`（渲染角色卡为 prompt 文本）

- [x] **Step 1: prompt**——`character_card_update_prompt`：输入旧角色卡 JSON + 本章草稿 + 出场角色 → 输出更新后角色卡 JSON（含 profile/current_state/relations/known/last_appearance/trajectory）

- [x] **Step 2: `update_character_cards`**
  - 读 characters 资产（JSON 或旧文本）
  - 旧文本 → 首次更新时自动迁移为角色卡结构
  - 调 LLM 更新 → `_parse_llm_json` → 双通道存回（content_json=卡片 / content_text=渲染）
  - 失败回退：保留旧状态，不抛异常

- [x] **Step 3: `load_active_character_cards`**
  - 读 characters 资产
  - 从上一章 actual_summary_json.characters 确定出场角色名（取交集）
  - `_render_character_cards` 只渲染出场角色卡 → 返回文本
  - 旧文本 → 原样返回（降级）

- [x] **Step 4: 测试**——mock LLM 测 update（含旧文本→JSON 迁移、失败回退）；load 只渲染出场角色；兼容（17 用例）

- [x] **Step 5: 测试 + Commit**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/tests/
git commit -m "feat: character cards system (update + active loading)"
```

---

### Task 2: task_service 接入

**Files:**
- Modify: `backend/app/services/task_service.py`（run_chapter_task / run_batch_chapters_task）

**Interfaces:**
- Consumes: `update_character_cards` / `load_active_character_cards`（Task 1）

- [x] **Step 1: 接入**——章节生成前：`character_state_text = await load_active_character_cards(...)`（替代直接读 characters 资产全文）；章节生成后：`update_character_cards(...)` 替代 update_character_state 存回；批量移除内存累积
  - 兼容：若 load 返回空/降级，行为与现在一致

- [x] **Step 2: 验证**——全量单测 198 通过（本机 venv 补齐 asyncpg/redis 等缺失依赖）

- [x] **Step 3: Commit**

```bash
git add backend/app/services/task_service.py
git commit -m "feat: wire character cards into chapter generation"
```

---

### Task 3: 验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`

- [x] **Step 1: 端到端**（可选，已跳过）——真实生成 2 章需真实 LLM + 容器，本机不可行；以全量单测回归代替（含双通道写回、旧文本迁移、逐章加载等断言）
- [x] **Step 2: 回归**——后端全量测试 198 通过
- [x] **Step 3: CHANGELOG**——「V3 P2-B：角色卡系统」
- [x] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record V3 P2-B character cards"
```

---

## 验收清单

- [x] characters 资产为结构化 JSON 角色卡（双通道：content_json 卡片 + content_text 渲染）
- [x] 每章写后角色卡更新（状态/关系/known/出场）
- [x] 写前只加载出场角色卡
- [x] 旧文本 characters 兼容（降级注入，不崩溃；首次更新自动迁移）
- [x] 既有功能回归正常（全量 198 用例通过）
