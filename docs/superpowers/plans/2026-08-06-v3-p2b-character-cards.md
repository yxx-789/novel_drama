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

- [ ] **Step 1: prompt**——`character_card_update_prompt`：输入旧角色卡 JSON + 本章草稿 + 出场角色 → 输出更新后角色卡 JSON（含 profile/current_state/relations/known/last_appearance/trajectory）

- [ ] **Step 2: `update_character_cards`**
  - 读 characters 资产（JSON 或旧文本）
  - 旧文本 → 尝试 LLM 转 JSON（一次）或降级
  - 调 LLM 更新 → `_parse_llm_json` → 存回 characters 资产（JSON）
  - 失败回退：保留旧状态，不抛异常

- [ ] **Step 3: `load_active_character_cards`**
  - 读 characters 资产
  - 从上一章 actual_summary_json.characters（或目录本章简介）确定出场角色名
  - `_render_character_cards` 只渲染出场角色卡 → 返回文本
  - 旧文本 → 原样返回（降级）

- [ ] **Step 4: 测试**——mock LLM 测 update（含旧文本→JSON 转换、失败回退）；load 只渲染出场角色；兼容

- [ ] **Step 5: 测试 + Commit**

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

- [ ] **Step 1: 接入**——章节生成前：`character_state_text = await load_active_character_cards(...)`（替代直接读 characters 资产全文）；章节生成后：`update_character_cards(...)` 替代 update_character_state 存回
  - 兼容：若 load 返回空/降级，行为与现在一致

- [ ] **Step 2: 验证**——容器 import + 单测

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/task_service.py
git commit -m "feat: wire character cards into chapter generation"
```

---

### Task 3: 验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 端到端**（可选）——真实生成 2 章，检查 characters 资产是 JSON 角色卡、写前只加载出场角色
- [ ] **Step 2: 回归**——后端全量测试
- [ ] **Step 3: CHANGELOG**——「V3 P2-B：角色卡系统」
- [ ] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record V3 P2-B character cards"
```

---

## 验收清单

- [ ] characters 资产为结构化 JSON 角色卡
- [ ] 每章写后角色卡更新（状态/关系/known/出场）
- [ ] 写前只加载出场角色卡
- [ ] 旧文本 characters 兼容（降级注入，不崩溃）
- [ ] 既有功能回归正常
