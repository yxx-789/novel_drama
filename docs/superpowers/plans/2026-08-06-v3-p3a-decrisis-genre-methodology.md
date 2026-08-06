# V3 P3-A 实施计划：去危机化 + 题材化伏笔/节奏方法论层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [x]`) syntax.

**Goal:** 把生成系统从"危机形状神经"改为按题材/结构自适应：structure 条件化去掉上游硬危机规则；新增题材伏笔/节奏参数表与钩子四断法；记忆描述性中性化。**单章生成不新增 LLM 调用**；旧项目兼容。

**Architecture:** 新增 `genre_methodology.py`（题材参数表 + 渲染）+ `structure_guidance.py`（按 structure 出 6 分片）；`prompts.py` 硬危机规则改条件占位符；`generation_service` 组装时注入；`task_service` 透传 structure。

**Tech Stack:** Python + FastAPI（既有）。

## Global Constraints

- **不新增 LLM 调用**（只改 prompt 拼装）
- 旧项目（无 writing_config / structure 缺省）回退危机基线，行为不变
- 不破坏既有功能（生成/记忆/短剧/导出/AI问答）
- 文案不出现「小红书」；后端测试通过
- 更新 `docs/CHANGELOG.md` 与路线图（`docs/superpowers/specs/2026-08-06-v3-p3-memory-quality-roadmap.md`）

---

### Task 1: 题材方法论模块 `genre_methodology.py`

**Files:**
- Create: `backend/app/generator/genre_methodology.py`

**Interfaces:**
- `get_genre_methodology(genre: str) -> dict`
- `_render_genre_methodology(genre: str) -> str`
- `HOOK_FOUR_BREAKS: list[str]`
- `DEFAULT_METHODOLOGY: dict`

- [x] **Step 1: 参数表**——12 题材全配：`conflict_driver` / `foreshadowing_intervals` / `touch_every` / `recovery_audit` / `hook_preference` / `payoff_note` / `opening_arc`（参照 spec §3.1 样例；悬疑/言情/玄幻/种田给满细节，其余题材按同类结构补全；缺权威方法的题材用保守默认并注释出处等级 B/C，不允许留空）
- [x] **Step 2: `get_genre_methodology`**——未知题材返回 `DEFAULT_METHODOLOGY`（不报错）
- [x] **Step 3: `_render_genre_methodology`**——渲染成 2-4 句 prompt 片段（伏笔回收间距 / 爽点频率 / 冲突驱动类型 / 钩子偏好）
- [x] **Step 4: 测试**——12 题材非空、渲染含关键参数、未知题材回退
- [x] **Step 5: Commit**

```bash
git add backend/app/generator/genre_methodology.py backend/app/tests/
git commit -m "feat: genre methodology table + hook four breaks"
```

---

### Task 2: structure 条件化 `structure_guidance.py`

**Files:**
- Create: `backend/app/generator/structure_guidance.py`
- Modify: `backend/app/generator/prompts.py`

**Interfaces:**
- `build_structure_guidance(structure: str | None) -> dict`（6 键：seed/character/world/first_chapter/chapter/blueprint）

- [x] **Step 1: 模块**——`CRISIS_STRUCTURES` / `CALM_STRUCTURES` 常量；`build_structure_guidance` 返回危机基线（=现状文本）与平静版分片（日常流/群像交织语义：不强制异常征兆/打破平衡/悬念曲线，保留人物魅力+生活切片+正反馈）
- [x] **Step 2: prompts.py 改造**——7 处硬危机规则改条件占位符：
  - `core_seed_prompt` L22-23 → `{structure_seed_guidance}`
  - `character_dynamics_prompt` L56-63 → `{structure_character_guidance}`
  - `world_building_prompt` L90-100 → `{structure_world_guidance}`
  - `first_chapter_draft_prompt` L135-139 → `{structure_first_chapter_guidance}`
  - `next_chapter_draft_prompt` L179-181 → `{structure_chapter_guidance}`
  - `chapter_blueprint_prompt` L325-355 → `{structure_blueprint_guidance}`
  - `architecture_consistency_prompt` L238 → 中性文本（"核心种子的主题/创作意图在架构中得到体现"，不再要求"危机体现"）
- [x] **Step 3: 题材方法论 + 钩子四断法注入**——`first_chapter_draft_prompt` / `next_chapter_draft_prompt` 新增 `{genre_methodology}` 占位符（渲染题材参数）；`next_chapter_draft_prompt` 的悬念钩子参考式升级为四断法枚举 + `{hook_preference}`
- [x] **Step 4: 测试**——6 结构分类正确；`None` 回退危机基线；新占位符在 format 时有值；一致性 prompt 无"危机体现"
- [x] **Step 5: Commit**

```bash
git add backend/app/generator/structure_guidance.py backend/app/generator/prompts.py backend/app/tests/
git commit -m "feat: structure-conditional guidance, de-crisis hard rules"
```

---

### Task 3: generation_service / task_service 接线

**Files:**
- Modify: `backend/app/services/generation_service.py`
- Modify: `backend/app/services/task_service.py`

**Interfaces:**
- `generate_architecture` / `generate_directory` / `generate_chapter_draft`：读取 `writing_config.structure`，调用 `build_structure_guidance` + `_render_genre_methodology`，把新占位符传入各 `prompt.format()`
- `task_service`：`_prompt_context_for_project` / 各 run 函数透传 structure（旧项目无 writing_config → 走默认危机基线）

- [x] **Step 1: `_prompt_context_for_project` 扩展**——返回结构（或新增 `_structure_guidance_for_project(project) -> dict`），兼容无 writing_config
- [x] **Step 2: `generate_architecture`**——`core_seed` / `character_dynamics` / `world_building` / `plot_architecture` / `create_character_state` 的 format 传入对应分片
- [x] **Step 3: `generate_directory`**——`chapter_blueprint_prompt` 传入 blueprint 分片
- [x] **Step 4: `generate_chapter_draft`**——`first/next_chapter` 传入 structure 分片 + `genre_methodology` 片段
- [x] **Step 5: 记忆中性化**——`extract_world_state_delta_prompt` / `build_state_summary_prompt` 追加平静结构约束（按 structure 传参控制）；`slim_state` 平静结构保留常态条目（规则简单）
- [x] **Step 6: 验证**——后端容器 import + 全部单测通过；抽查 1 章输出确认注入生效（日志或 `_render_genre_methodology` 单元断言）
- [x] **Step 7: Commit**

```bash
git add backend/app/services/generation_service.py backend/app/services/task_service.py backend/app/tests/
git commit -m "feat: wire structure guidance + genre methodology into generation"
```

---

### Task 4: 验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-08-06-v3-p3-memory-quality-roadmap.md`（阶段 2 勾选状态）

- [x] **Step 1: 端到端（prompt 级验证）**——日常流/群像交织与悬疑项目的组装 prompt 已由 `test_p3a_wiring.py` 断言注入正确分片/题材方法论/钩子偏好；**真实 LLM 出稿抽查待配 API key 后人工执行**（建日常流项目生成 2-3 章看正文无"异常征兆/打破平衡"硬痕迹、悬疑项目保留悬念与伏笔回收）
- [x] **Step 2: 回归**——旧项目（无 writing_config）生成正常（回退危机基线）
- [x] **Step 3: 速度确认**——单章生成 LLM 调用数 ≤6（不增）
- [x] **Step 4: CHANGELOG**——「V3 P3-A：去危机化 + 题材化伏笔/节奏方法论」
- [x] **Step 5: Commit**

```bash
git add docs/CHANGELOG.md docs/superpowers/
git commit -m "docs: record V3 P3-A de-crisis + genre methodology"
```

---

## 验收清单

- [x] 日常流/群像交织项目章节无危机硬规则痕迹；升级打怪/悬疑保留危机推进（**prompt 级已验证**：平静分片不含正向危机语义；正文级待真 LLM 出稿抽查）
- [x] 题材参数表 12 题材全有值（单元测试强制），抽查 ≥2 题材正文匹配（**prompt 注入级已验证**；正文匹配待真 LLM）
- [x] 章末钩子按题材偏好落在四断法之一（**prompt 注入级已验证**：悬疑注入「发现、误判」优先；正文落点待真 LLM）
- [x] 单章生成 LLM 调用数不变（≤6）（基线 af7b165 vs 当前均为 14 处 `_invoke_with_retry`，P3-A 未新增调用）
- [x] 旧项目回退兼容；后端测试通过（230 passed）
