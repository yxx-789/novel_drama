# V3 P2-A 实施计划：结构化章节记忆（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 每章写后 LLM 提取结构化章节记忆（摘要/结尾钩子/出场角色/关系变化/新伏笔），存 `Chapter.actual_summary_json`；下一章用真实摘要替代计划 outline；前章窗口动态化。

**Architecture:** `Chapter.actual_summary_json`(JSONB) 存结构化记忆；新 prompt `chapter_memory_extract_prompt`；`_chapter_excerpt` 动态窗口；`task_service` 生成草稿后提取摘要存库，下一章用 `actual_summary_json.summary`（回退 outline）。

**Tech Stack:** Python + SQLAlchemy 2.0 + Alembic。

## Global Constraints

- 实际摘要 = 一次额外 LLM 调用/章（可接受）
- 旧项目（无 actual_summary_json）回退 outline，行为兼容
- 不破坏既有功能（生成/记忆/短剧）
- 文案不出现「小红书」；后端测试通过
- 更新 `docs/CHANGELOG.md`

---

### Task 1: 数据模型

**Files:**
- Modify: `backend/app/models/project.py`（Chapter 加 `actual_summary_json` JSONB）
- Create: Alembic 迁移

- [ ] **Step 1: 模型**——Chapter 加 `actual_summary_json: Mapped[dict | None] = mapped_column(JSONB)`
- [ ] **Step 2: 迁移**——autogenerate + upgrade + 验证 `\d chapters`
- [ ] **Step 3: Commit**

```bash
git add backend/app/models/project.py backend/alembic/versions/
git commit -m "feat: add actual_summary_json to Chapter"
```

---

### Task 2: 动态前章窗口

**Files:**
- Modify: `backend/app/services/generation_service.py`

**Interfaces:**
- Produces: `_chapter_excerpt(draft: str | None) -> str`（结尾 20%，下限 800 上限 2000）

- [ ] **Step 1: 实现**

```python
def _chapter_excerpt(draft: str | None) -> str:
    """取章节结尾做衔接上下文：结尾 20%，下限 800 字，上限 2000 字。"""
    if not draft:
        return ""
    length = len(draft)
    if length <= 800:
        return draft
    window = max(800, min(2000, int(length * 0.2)))
    return draft[-window:]
```

- [ ] **Step 2: 替换 `generate_chapter_draft` 里的 `previous_chapter_draft[-1500:]`**（用 `_chapter_excerpt`）

- [ ] **Step 3: 测试**——`test_block_library.py` 或新 `test_memory.py` 加：短章全量、长章 20% 且封顶、空输入返回空

- [ ] **Step 4: 测试 + Commit**

```bash
git add backend/app/services/generation_service.py backend/app/tests/
git commit -m "feat: dynamic previous-chapter excerpt window"
```

---

### Task 3: 结构化摘要提取 + 管线接入

**Files:**
- Modify: `backend/app/generator/prompts.py`（新增 `chapter_memory_extract_prompt`）
- Modify: `backend/app/services/generation_service.py`（新增 `extract_chapter_memory`）
- Modify: `backend/app/services/task_service.py`（run_chapter_task / run_batch_chapters_task 接入）

**Interfaces:**
- Consumes: `Chapter.actual_summary_json`（Task 1）
- Produces:
  - `extract_chapter_memory(db, chapter, llm_config) -> dict`（结构化记忆：summary/hook/characters/relations_changed/foreshadowing_added/connects_to）
  - 章节生成时 `previous_chapter_summary = prev.actual_summary_json["summary"] or prev.outline or ""`

- [ ] **Step 1: prompt**

```python
chapter_memory_extract_prompt = """\
作为资深小说编辑，请阅读以下章节正文，提取结构化记忆，供后续章节保持连贯。

【章节正文】
{chapter_text}

只返回 JSON，格式：
{{
  "summary": "150-300字精炼摘要：本章实际发生了什么（事件/冲突/结果）",
  "hook": "本章结尾留下的悬念钩子",
  "characters": ["出场角色名"],
  "relations_changed": {{"角色A-角色B": "关系变化描述"}},
  "foreshadowing_added": [{{"name": "伏笔名", "note": "埋设说明"}}],
  "connects_to": "留给下一章的续接点（下章该从哪继续）"
}}
仅返回 JSON。
"""
```

- [ ] **Step 2: `extract_chapter_memory` 函数**——调 LLM → `_parse_llm_json`（已有）→ 返回 dict；失败回退 `{"summary": chapter 前 300 字}` 或空 dict

- [ ] **Step 3: task_service 接入**
  - `run_chapter_task` / `run_batch_chapters_task`：草稿生成后 → `extract_chapter_memory` → 存 `chapter.actual_summary_json`（仅 success 提取时存）
  - 下一章：`previous_summary = prev.actual_summary_json["summary"] if prev.actual_summary_json else prev.outline or ""`

- [ ] **Step 4: 测试**——extract 函数 mock 测试 + 管线逻辑（前章 actual_summary 优先于 outline）

- [ ] **Step 5: 验证**——后端容器 import + 单测通过

- [ ] **Step 6: Commit**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/services/task_service.py backend/app/tests/
git commit -m "feat: structured chapter memory extraction"
```

---

### Task 4: 验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 端到端**——建项目 → 生成 2 章 → 检查第 2 章 `actual_summary_json` 非空、第 3 章生成时用了前章真实摘要（可看日志/worker 输出含 summary）
- [ ] **Step 2: 回归**——旧项目（无 actual_summary）生成正常（回退 outline）
- [ ] **Step 3: CHANGELOG**——「V3 P2-A：结构化章节记忆」
- [ ] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record V3 P2-A structured chapter memory"
```

---

## 验收清单

- [ ] `Chapter.actual_summary_json` 建库/读写正常
- [ ] 每章生成后 actual_summary_json 有结构化内容（summary/hook/characters 等）
- [ ] 下一章 previous_chapter_summary 用真实摘要（回退 outline）
- [ ] 动态前章窗口（20%/800-2000）
- [ ] 旧项目回退兼容；回归测试通过
