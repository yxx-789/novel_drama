# V3 P3-B 实施计划：记忆分层 + 伏笔台账

> **Goal:** 解决「长线稀释」与「伏笔/副线丢失」：arc 级摘要冻结（L2）+ 全书摘要合成（L3）+ 伏笔台账（追踪 触碰/回收/逾期/副线闲置）。
> **约束:** 单章生成**不新增 LLM 调用**（非 arc 边界 ≤6；arc 边界 ≤7，摊薄 1/N）；台账更新复用 `extract_chapter_memory`；旧项目兼容；不破坏既有功能；文案不出现「小红书」；后端测试通过。
> **设计:** `docs/superpowers/specs/2026-08-06-v3-p3b-memory-layering-ledger-design.md`（已定稿）。

**复核流程（用户要求）：** 每个 Task 完成（含测试通过）后，派发**独立复核子 agent** 做 code review（对照 spec 接口 / 查 bug / 回归既有功能 / 测试充分性 / 遵循 CLAUDE.md），复核通过后才提交。复核发现的问题修复后需复核 agent 确认或重审。

---

### Task 1: 伏笔台账纯规则模块 `foreshadowing_ledger.py`

**Files:**
- Create: `backend/app/generator/foreshadowing_ledger.py`
- Create: `backend/app/tests/test_foreshadowing_ledger.py`

**Interfaces:**
- `merge_foreshadowing_delta(ledger: dict, memory: dict, genre: str, chapter_num: int) -> dict`（纯规则，无 LLM）
- `build_foreshadowing_reminder(ledger: dict, current_chapter: int, methodology: dict) -> str`（纯规则）

- [x] **Step 1: `merge_foreshadowing_delta`**——`foreshadowing_added`（含 `known_by`）新增 entry（`status=open`，`planned_recovery_range` 按题材参数表 `foreshadowing_intervals.mid` 取，`last_touch_chapter`=本章；同名已存在则视为触碰合并）；`foreshadowing_touched` 匹配设 `status=touched` + 更新 `last_touch_chapter`（纯名字列表，**不携带 known_by**；仅同名重复 `added` 才合并 known_by，且已 recovered/abandoned 不重开）；`foreshadowing_recovered` 匹配设 `status=recovered`；`subplot_advanced` 匹配设 `subplot=true` + 更新触碰；匹配失败进 `unmatched`（不静默丢弃）
- [x] **Step 2: `build_foreshadowing_reminder`**——逾期未碰（`current_chapter - last_touch_chapter > touch_every[1]`）→「该碰一下」；进入回收窗口（`current_chapter ∈ planned_recovery_range` 且未回收）→「该考虑回收」；副线闲置（`subplot=true` 且闲置 >20 章）→「已闲置 N 章」；无内容返回空串
- [x] **Step 3: 测试**——新增/触碰/回收/逾期状态迁移、known_by 合并、命名漂移进 unmatched、reminder 三类命中与空串
- [x] **Step 4: 复核子 agent + Commit**

```bash
git add backend/app/generator/foreshadowing_ledger.py backend/app/tests/
git commit -m "feat: foreshadowing ledger pure-rule module"
```

---

### Task 2: prompts 扩展 + arc 摘要函数

**Files:**
- Modify: `backend/app/generator/prompts.py`
- Modify: `backend/app/services/generation_service.py`
- Create: `backend/app/tests/test_arc_summary.py`

**Interfaces:**
- `chapter_memory_extract_prompt` 扩展输出字段：`foreshadowing_touched` / `foreshadowing_recovered` / `subplot_advanced` / `foreshadowing_added[].known_by`
- 新增 `build_arc_summary_prompt` / `synthesize_book_summary_prompt`
- `extract_chapter_memory` 解析新字段（容忍缺失，旧输出兼容）
- 新增 `build_arc_summary(chapters, llm_config, arc_size=None)` / `synthesize_book_summary(arcs, llm_config)`

- [x] **Step 1: `chapter_memory_extract_prompt` 扩展**——在既有 JSON 格式追加 `foreshadowing_touched`（推进/提及既有伏笔）/ `foreshadowing_recovered`（回收既有伏笔）/ `subplot_advanced`（推进的副线）/ `foreshadowing_added[].known_by`（谁知晓该伏笔/秘密）
- [x] **Step 2: 新增 arc 摘要 prompt**——`build_arc_summary_prompt`（输入本 arc 各章 actual_summary_json，输出该 arc 摘要 + 关键事件/人物/伏笔列表）；`synthesize_book_summary_prompt`（输入各 arc 摘要，输出全书摘要）
- [x] **Step 3: `extract_chapter_memory` 解析新字段**——容忍缺失：无 `foreshadowing_touched` 等字段时返回空列表/空 dict，台账合并跳过；不改变既有返回 dict 行为
- [x] **Step 4: 新增 `build_arc_summary` / `synthesize_book_summary`**——mock LLM 路径：未配置 / 调用失败 / 空返回 → 返回空 dict（调用方不写入），不抛异常
- [x] **Step 5: 测试**——`test_arc_summary.py`：build_arc_summary 成功/失败回退、synthesize 合成、extract_chapter_memory 新字段解析与缺失容错
- [x] **Step 6: 复核子 agent + Commit**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py backend/app/tests/
git commit -m "feat: memory extract new fields + arc/book summary functions"
```

---

### Task 3: task_service 接线 + 资产白名单

**Files:**
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/routers/assets.py`（ASSET_TYPES 白名单）

- [x] **Step 1: arc 边界触发**——常量 `ARC_SIZE = 15`（模块内，可配置化）；`run_chapter_task` / `run_batch_chapters_task` 中 `chapter_num % ARC_SIZE == 0` 时：读本 arc 各章 `actual_summary_json` → `build_arc_summary` → 写入 `arc_summaries` 资产（arcs 数组追加 + 冻结不覆盖；book_summary 由批量循环结束时 `_synthesize_book_summary_asset` 合成一次）；arc 摘要生成失败不中断生成
- [x] **Step 2: 写前组装 L1/L2**——`previous_chapter_summary` 维持 L1（上一章实际摘要，现状不变）；在 `world_state_summary` 尾部追加「已冻结 arc 摘要」（最近完成 arc，若存在）与「伏笔/副线提醒」（`build_foreshadowing_reminder` 结果，非空时），零 prompt 占位符改动
- [x] **Step 3: 台账合并**——写后提取 `extract_chapter_memory` 后调用 `merge_foreshadowing_delta` 合并到 `foreshadowing` 资产（content_json）；无资产自动初始化空结构；失败不中断生成
- [x] **Step 4: ASSET_TYPES 白名单**——`routers/assets.py` 新增 `arc_summaries` / `foreshadowing`
- [x] **Step 5: 测试**——旧项目（无新资产）生成行为不变；arc 边界触发（mock）；台账合并写回；LLM 调用数断言（非边界 ≤6，边界 ≤7）
- [x] **Step 6: 复核子 agent + Commit**

```bash
git add backend/app/services/task_service.py backend/app/routers/assets.py backend/app/tests/
git commit -m "feat: wire arc summaries + foreshadowing ledger into chapter pipeline"
```

---

### Task 4: 验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-08-06-v3-p3-memory-quality-roadmap.md`（阶段 3 状态）
- Modify: `memory-bank/progress.md` / `memory-bank/decisions.md`

- [x] **Step 1: 回归**——全量测试通过；旧项目（无 arc_summaries/foreshadowing 资产）生成行为不变；`extract_chapter_memory` 旧格式解析容错
- [x] **Step 2: LLM 调用数断言**——单章（非 arc 边界）= 现状 ≤6；arc 边界 = ≤7（含 arc 摘要，摊薄 1/N）；verification 用例计入测试
- [x] **Step 3: CHANGELOG**——「V3 P3-B：记忆分层 + 伏笔台账」
- [x] **Step 4: plan 全勾选 + roadmap 阶段 3 状态 →「已实现」+ memory-bank 同步**（progress P3-B、decisions D018）
- [x] **Step 5: 复核子 agent + Commit**

```bash
git add docs/CHANGELOG.md docs/superpowers/ memory-bank/
git commit -m "docs: record V3 P3-B memory layering + foreshadowing ledger"
```

---

## 验收清单

- [ ] 30 章 + 项目：arc 摘要仍保留前 10 章关键事件（不被逐章覆盖稀释）——**实现级验证已通过**（arc 冻结不覆盖逻辑 + 单元测试 `test_boundary_frozen_not_overwritten`）；真实 30 章出稿抽查待配 API key
- [x] 伏笔台账逐章更新，逾期/待回收/副线闲置在写前上下文出现——**纯规则单测验证**（`test_foreshadowing_ledger.py` + `test_p3b_wiring.py`）
- [x] 单章 LLM 调用数不变（非边界 ≤6，arc 边界 ≤7）——**调用点计数断言**（`test_llm_call_count_non_boundary_6` / `test_llm_call_count_arc_boundary_7`）
- [x] 旧项目兼容回归通过（`test_old_project_no_new_assets_no_llm_overhead` + 全量 290）
