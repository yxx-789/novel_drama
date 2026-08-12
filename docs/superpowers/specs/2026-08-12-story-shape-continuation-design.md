# 故事形态（短篇完结 / 连载开篇）与续写闭环 — 设计文档

> **日期**：2026-08-12
> **状态**：已批准（分节确认）

## 背景与问题

生成架构时，情节架构模板（`plot_architecture_prompt`）缺少 `number_of_chapters` 参数，模型会按"整部长篇"的刻板印象自由发挥（实测生成过五卷 500 章的版图），而用户创建项目时只选了 20/30 章。导致：

1. **架构与目录脱节**：架构讲 500 章的故事，目录只有 20 章，卷目划分、伏笔回收周期排不下。
2. **用户意图被猜测**：用户选 20 章，语义可能是"这本书就 20 章"（要完整结局），也可能是"先写 20 章看反响"（要留钩子可续写）。生成时无法区分。

**核心决策：意图前置收敛**——创建项目时让用户显式声明两个意图，之后所有生成环节按声明执行，而不是让模型生成时猜测。

## 三个前置收敛决策

1. **故事形态 `story_shape`**（创建必选）：
   - `'final'` 短篇完结 —— 填的 N 章即整本书，第 N 章是真正的结局
   - `'open'` 连载开篇 —— 先写 N 章看反响，第 N 章留钩子，后续续写
2. **全书目标总章数 M `total_chapters_target`**（open 模式必填，自由数字 10~1000 且 M > N）：
   - 架构版图按 M 章设计（锚定用户声明的边界，而非模型自由发挥）
   - **创建后锁定不可修改**（前端禁用 + 后端拒绝 PATCH）
3. **结局章模式**（由形态派生）：
   - `final`：情节架构 20 章闭环——卷目总和 = N，主线 N 章内走完，伏笔 N 章内全回收，第 N 章情感+剧情双收束；世界观/角色保留纵深
   - `open`：情节架构按 M 章设计全书版图，标注当前阶段 = 前 N 章；第 N 章阶段性收束 + 留 1-3 个续写钩子；第 M 章为全书终点（结局写法）

## 数据模型

`projects` 表新增两列：

| 字段 | 类型 | 约束 | 语义 |
|---|---|---|---|
| `story_shape` | VARCHAR(20) | NOT NULL | `'final'` / `'open'`；创建必选；允许 PATCH 修改 |
| `total_chapters_target` | INTEGER | NULL；open 必填 | 全书目标总章数 M；10~1000 且 > num_chapters；创建后不可修改；final 为 NULL |

**Alembic 迁移**：加两列；存量项目回填 `story_shape='open'`、`total_chapters_target=NULL`（现有项目已生成 500 章级架构，天然是连载形态；M 为 NULL 视为"未声明目标"，续写不设上限）。

## API

- `POST /projects`：
  - `story_shape` 必填（缺失 → 422）
  - `story_shape='open'` 时必须带 `total_chapters_target`，且 10 ≤ M ≤ 1000、M > num_chapters（违反 → 422）
- `PATCH /projects/{id}`：
  - **拒绝修改 `total_chapters_target`**（400："全书目标章数创建后不可修改"）
  - `story_shape` 可改：`open→final` 自动清空 M；`final→open` 必须补传 M
  - 修改只影响后续新生成的内容；已生成的架构/目录/章节不动

## 生成链路改造

### A. 架构生成（`generate_architecture`）

从 project 读取 `story_shape`、`total_chapters_target`，注入两处：

**Step 1 核心种子**的篇幅表述：
- `final`：`篇幅：约 {N} 章（每章 {word_number} 字），本书 {N} 章内完结`
- `open`：`当前阶段约 {N} 章，全书规划约 {M} 章，请按全书规模设计`

**Step 4 情节架构**注入形态指令块（新增 `_architecture_shape_instruction()` helper）：
- `final`：全书卷目划分总和 = N；主线在 N 章内走完；所有伏笔在 N 章内回收；第 N 章情感+剧情双收束（真正结局）
- `open`：全书卷目划分总和 = M；标注"当前阶段 = 前 N 章（全书第一阶段）"；第 N 章为阶段收束点，预留后续卷目的钩子

世界观/角色：两种模式都保留纵深，不限制设定深度。

### B. 目录生成（`generate_directory`）

注入第 N 章要求（新增 `_directory_shape_instruction()` helper）：
- `final`：第 N 章必须为**结局章**——主线闭合、情感收束、列出伏笔回收清单
- `open`：第 N 章**阶段性收束**，明确留下 1-3 个续写钩子（未解之谜 / 新线索 / 暗线推进）

### C. 续写闭环（新任务类型 `continue_writing`）

**前置校验**（在路由/任务入口）：`project.story_shape == 'open'`；若 M 存在则 `num_chapters < M`；续写 k 满足 `1 ≤ k ≤ M - num_chapters`（M 为 NULL 时不限上限）。

**任务步骤**（一个 worker 任务串行执行；**只追加目录，不生成正文**——正文由用户确认目录后在章节页「AI 批量生成」触发，增量语义跳过已有 draft）：
1. 更新 `projects.num_chapters = N + k`
2. **追加目录**：新增 `append_directory_prompt` 模板
   - 输入：架构版图（M 章）+ 已有目录（前 N 章定稿）+ 第 N 章结尾状态
   - 要求：只输出第 N+1 ~ N+k 章；衔接已有节奏曲线与伏笔；若 N+k == M 则按结局章设计，否则阶段收束 + 留钩子
   - `_ensure_chapters` 追加语义：**已存在章节跳过不动**（保护定稿，不覆盖标题/大纲）
   - 目录资产累积落库（既有定稿 + 新增片段）
3. 任务完成（`progress=100`）；正文由章节页 `batch_chapters` 批量生成（增量：只处理 `draft` 为空 / 未完成的章节）

### D. 正文生成

- 批量任务改为增量语义：只生成未完成的章节
- 第 M 章结局：不做正文 prompt 特殊分支（YAGNI）——目录第 M 章简述写明结局，正文消费目录简述 + 世界状态摘要自然按结局写

### E. 校验

`architecture_consistency_prompt` 是死代码，本期不启用（YAGNI）。形态指令在 prompt 层自洽。

## 前端交互

| 位置 | 改动 |
|---|---|
| ProjectCreate | 章数/字数下新增「故事形态」单选（必选，不选不能提交）：`短篇完结（N 章即结局）/ 连载开篇（先写 N 章可续写）`；选连载时展开「全书目标总章数 M」输入（必填，10~1000 且 > N），附提示"该数字创建后不可修改，请谨慎填写" |
| OverviewTab | 形态可改（弹确认："影响后续生成的架构/目录，重新生成后生效"）；`open→final` 自动清空 M；`final→open` 必须补填 M；M 只读展示（锁定 + "创建后不可修改"） |
| 续写入口 | 连载形态且 `num_chapters < M` 时，目录 tab 显示「续写」按钮 → 弹窗输入续写章数 k（1 ≤ k ≤ M−N）→ 创建 `continue_writing` 任务 → 轮询进度；达到 M 后禁用并提示"已到全书规划终点" |

## 测试

| 层 | 用例 |
|---|---|
| 后端 API | open 缺 M → 422；M 超范围或 ≤N → 422；PATCH 改 M → 400；final 不带 M → 正常 |
| 后端迁移 | 加列 + 存量回填 `'open'/NULL` |
| 后端 prompt | mock LLM 断言架构/目录 prompt：final 注入闭环指令、open 注入版图+阶段标注指令（指令块内容差异） |
| 后端续写任务 | 追加目录不覆盖已有章节；增量正文跳过已有 draft；`num_chapters` 更新；k > M−N 拒绝 |
| 前端 | 创建表单校验（形态必选、M 必填）、续写弹窗校验；`tsc + build` 通过 |

## 文档

- `docs/DATA_MODEL.md`：projects 表新增两列
- `docs/API_SPEC.md`：create/update schema、continue_writing 任务类型
- `docs/CHANGELOG.md`：变更记录
- `docs/ARCHITECTURE.md`：生成链路形态消费简述

## 范围

本期实现：数据模型 + API + 前端创建/设置 + 架构/目录按形态生成 + 续写闭环（continue_writing 任务 + 追加目录 + 增量正文 + 前端入口）。

不实现：正文第 M 章特殊分支（YAGNI）、architecture_consistency 启用（死代码）、M 中途修改（设计上禁止）。
