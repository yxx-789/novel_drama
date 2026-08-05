# V3 P1 实施计划：积木库 + 创作意图（V2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⚠️ 质量底线（务必遵守项目 CLAUDE.md「V3 生成系统开发专项原则」）：**
> 本计划的核心是积木库内容。**每块积木必须内容完整、有深度、不敷衍**——不是占位符、不是一句泛化话术。宁可分批交付，绝不降质。子 agent 必须如实报告，不得悄悄简化。

**Goal:** 把生成系统改造成积木式配置——用户层 7 维正交积木 + 内部细粒度风味库 + 创作意图（剧情走向）最高优先注入 + 减法 prompt。

**Architecture:** `Project.writing_config`(JSONB) 存用户选择；`block_library.py` 定义积木库并组装「写作上下文」；generation_service 读取 config 注入所有生成环节；删除 prompt 里的硬结构规则，改为参考式积木片段。

**Tech Stack:** Python + SQLAlchemy 2.0 + Alembic + React/TypeScript。

## Global Constraints

- 积木内容**完整有深度**（见上质量底线），正交不重叠
- 优先级：创作意图 ＞ 自定义字段 ＞ 题材默认 ＞ 内部风味 ＞ 积木通用
- 用户给了 `剧情走向` 时必须**高优先注入、不得偏离**
- 文案不出现「小红书」字样
- 不破坏既有功能（灵感/主页/AI 助手/短剧/导出）
- 前端 `npm run build` 零错误、后端测试通过
- 更新 `docs/CHANGELOG.md`

---

### Task 1: 数据模型——Project.writing_config

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/schemas/project.py`
- Create: `backend/alembic/versions/xxxx_add_project_writing_config.py`（autogenerate）

**Interfaces:**
- Produces: `Project.writing_config: dict|None`（JSONB）；`ProjectCreate.writing_config` / `ProjectUpdate.writing_config`

- [ ] **Step 1: 模型加字段**

```python
# app/models/project.py，class Project 内
writing_config: Mapped[dict | None] = mapped_column(JSONB)
```
（`JSONB` 已在 models/project.py import）

- [ ] **Step 2: schema 加字段**

```python
# ProjectCreate / ProjectUpdate 加
writing_config: dict | None = None
```

- [ ] **Step 3: 迁移**

```bash
docker compose exec -T backend alembic revision --autogenerate -m "add project writing config"
docker compose exec -T backend alembic upgrade head
docker compose exec -T db psql -U postgres -d ai_novel_studio -c "\d projects" | grep writing_config
```

- [ ] **Step 4: service 传递**——`project_service.create_project` 把 `project_in.writing_config` 写入 Project

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/project.py backend/app/schemas/project.py backend/alembic/versions/ backend/app/services/project_service.py
git commit -m "feat: add writing_config to Project"
```

---

### Task 2: 积木库——用户层 7 维（质量核心，内容要深）

**Files:**
- Create: `backend/app/generator/block_library.py`

**Interfaces:**
- Produces:
  - `DIMENSION_OPTIONS: dict`（各维度可用选项）
  - 每维的积木块：`CORE_GENRE_BLOCKS` / `BACKGROUND_BLOCKS` / `HOOK_BLOCKS` / `STRUCTURE_BLOCKS` / `STYLE_BLOCKS` / `AUDIENCE_BLOCKS` / `CAST_SCALE_BLOCKS`
  - 每块含：`prompt_fragment: str`（注入 prompt 的参考片段，内容完整有深度）
  - `DEFAULT_RECIPES: dict`（每个核心题材的默认配方）
  - `build_context(config: dict) -> str`（把 config 拼成「写作上下文」文本）

**质量要求（每块积木必须有深度，示例）：**

`CORE_GENRE_BLOCKS["玄幻"]` 的 `prompt_fragment` 需包含（非示例，是要求）：
- 文风特征（如"恢弘大气、境界感、热血攀升"——要具体，不要"文风匹配题材"式空话）
- 核心卖点/常见套路（金手指/升级/奇遇/宗门等，给出 3-5 个具体套路）
- 典型场景（宗门大比/秘境/突破/夺宝等）
- 避雷（忌流水账升级、忌主角无敌无冲突等）
- 伏笔手法倾向（境界伏笔/宝物伏笔等）

**其他维度每块也要有相应深度**：
- `AUDIENCE_BLOCKS`：句长要求（短句/可复杂）、爽点密度（几章一爽）、逻辑权重、铺陈容忍、AI 味避雷侧重
- `STYLE_BLOCKS`：语调、节奏感、修辞倾向、叙事距离
- `STRUCTURE_BLOCKS`：章节组织方式、单元结构、收束方式
- `CAST_SCALE_BLOCKS`：角色数量范围、关系网复杂度
- `BACKGROUND_BLOCKS` / `HOOK_BLOCKS`：背景氛围 / 卖点套路各 2-4 个具体条目

**默认配方**：12 个核心题材各一份（含 文风/受众/规模 默认值）

- [ ] **Step 1: 写 block_library.py（内容要完整，可分多次 commit，但每次内容不能敷衍）**

- [ ] **Step 2: 自检**——每块积木的 prompt_fragment 长度 ≥ 50 字且包含具体信息（非空泛套话）；用脚本扫描检查无空/过短片段

- [ ] **Step 3: 单元测试** `backend/app/tests/test_block_library.py`
  - 每个维度的选项非空
  - 每块积木的 prompt_fragment 非空且长度达标
  - `build_context({...})` 能按 config 拼出包含对应积木文本的上下文
  - `DEFAULT_RECIPES` 覆盖全部核心题材

- [ ] **Step 4: 测试**——`docker compose exec -T backend python -m pytest app/tests/test_block_library.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/generator/block_library.py backend/app/tests/test_block_library.py
git commit -m "feat: user-layer block library (7 dimensions)"
```

---

### Task 3: 积木库——内部细粒度风味层

**Files:**
- Modify: `backend/app/generator/block_library.py`

**Interfaces:**
- Produces:
  - `INTERNAL_FLAVORS: dict`（按核心题材分组，每组 5-8 个细粒度风味块）
  - `roll_internal_flavor(config: dict) -> dict`（随机选 1 或组合 2-3 个风味，写回 config["internal_flavor"]）
  - `build_context` 把 internal_flavor 也拼进上下文

**质量要求**：每个风味块是具体、有辨识度的（如 玄幻 下：洪荒色彩/西游衍生/诸天万界/克苏鲁味/巫师/高武/盗墓——每块含 2-3 句具体特征，不是干词条）。

- [ ] **Step 1: 写 INTERNAL_FLAVORS + roll_internal_flavor**

- [ ] **Step 2: 测试**——`roll_internal_flavor` 返回合法结果、不越界；`build_context` 含风味文本

- [ ] **Step 3: Commit**

```bash
git add backend/app/generator/block_library.py
git commit -m "feat: internal flavor layer with random selection"
```

---

### Task 4: 减法 prompt + 生成管线注入

**Files:**
- Modify: `backend/app/generator/prompts.py`（删硬规则）
- Modify: `backend/app/services/generation_service.py`（注入写作上下文 + 创作意图）

**Interfaces:**
- Consumes: `build_context(config)`（Task 2/3）
- Produces: `generate_architecture` / `generate_directory` / `generate_chapter_draft` 接收 `writing_context` 参数并注入 prompt

- [ ] **Step 1: 删除 prompt 里的硬结构规则**
  - 架构/目录/章节 prompt 中删除：三幕式强制、"必须包含显性冲突与潜在危机"、"至少 1 个认知颠覆时刻"、"不要写总结性结尾，要在悬念最高点收束"、"每 3-5 章一个悬念单元"、"设计 3-6 个核心角色"
  - 保留轻骨架（呼应前文、章节有起落、围绕创作意图）

- [ ] **Step 2: 新增【写作上下文】占位符**——每个生成 prompt 加 `{writing_context}` 段（放在设定之后、写作要求之前），内容来自 `build_context`

- [ ] **Step 3: 新增【创作意图】占位符**——架构/目录/章节 prompt 加 `{creative_intent}` 段，措辞为"用户的创作意图，必须严格遵循，冲突时以此为准"

- [ ] **Step 4: generation_service 改造**
  - 各生成函数读取 `project.writing_config` → `build_context` 得到 `writing_context`
  - 读取 `project.writing_config["plot_direction"]` 得到 `creative_intent`
  - 注入对应 prompt 的占位符

- [ ] **Step 5: 验证**——后端容器 reload，`import` 通过；`build_context` 结果能正确格式化进 prompt（不报 KeyError）

- [ ] **Step 6: Commit**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py
git commit -m "feat: subtraction prompts + writing context injection"
```

---

### Task 5: 创作意图高优先注入

**Files:**
- Modify: `backend/app/generator/prompts.py`
- Modify: `backend/app/services/generation_service.py`

**Interfaces:**
- Consumes: `writing_config["plot_direction"]`
- Produces: 创作意图块注入所有生成环节，明确高优先

- [ ] **Step 1: 架构/目录/章节 prompt 的【创作意图】段写明优先规则**（"若与其它设定冲突，以此为准"）

- [ ] **Step 2: generation_service** 把 `plot_direction`（若非空）格式化为创作意图块；为空时输出占位符兜底文本

- [ ] **Step 3: 验证**——有/无 plot_direction 两种情况 prompt 都能正确组装

- [ ] **Step 4: Commit**

```bash
git add backend/app/generator/prompts.py backend/app/services/generation_service.py
git commit -m "feat: high-priority creative intent injection"
```

---

### Task 6: 前端创建项目页

**Files:**
- Modify: `frontend/src/pages/ProjectCreate.tsx`
- Modify: `frontend/src/api/project.ts`（ProjectCreate 接口加 writing_config）

**Interfaces:**
- Consumes: 后端 `writing_config` 字段（Task 1）
- Produces: 创建页支持 7 维选择 + 剧情走向 + 自定义字段 + 默认配方

- [ ] **Step 1: api/project.ts** 的 `CreateProjectRequest` 加 `writing_config?: object`

- [ ] **Step 2: ProjectCreate.tsx**
  - 基础区：名称/主题/**剧情走向**（textarea）
  - 「写作设置」折叠区：核心题材（单选，选了自动带出默认配方）+ 其他 6 维（可展开调整）
  - 「自定义设定」折叠区：核心卖点/独特设定/人物要求/避雷/自由补充
  - 提交时组装 `writing_config` 对象
  - 从灵感创建时（query 预填）保留现有逻辑

- [ ] **Step 3: 构建**——`cd frontend && npm run build` 零错误

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProjectCreate.tsx frontend/src/api/project.ts
git commit -m "feat: writing config form on project create"
```

---

### Task 7: 端到端验证 + 文档

**Files:**
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 实测**——建一个"玄幻+洪荒+金手指+轻松爽文"项目，生成架构 → 目录 → 1 章，检查：
  - 架构/章节包含写作上下文风味（非千篇一律）
  - 有剧情走向时生成遵循走向
  - 无硬规则痕迹（角色数可 >6、结构不强制三幕）

- [ ] **Step 2: 回归**——既有功能（灵感/主页/AI 助手/短剧）正常

- [ ] **Step 3: CHANGELOG** 记录「V3 P1：积木式生成」

- [ ] **Step 4: Commit**

```bash
git add docs/CHANGELOG.md
git commit -m "docs: record V3 P1 blocks and intent"
```

---

## 验收清单

- [ ] `writing_config` 建库/存取正常
- [ ] 积木库内容完整有深度（脚本扫描无空/过短片段；每块含具体信息）
- [ ] 减法 prompt：硬规则已删、轻骨架保留
- [ ] 写作上下文/创作意图正确注入所有生成环节
- [ ] 剧情走向高优先遵循
- [ ] 前端创建页支持 7 维 + 剧情走向 + 自定义 + 默认配方
- [ ] 生成效果不再千篇一律（题材/受众/文风差异明显）
- [ ] 既有功能回归；`npm run build` 零错误
