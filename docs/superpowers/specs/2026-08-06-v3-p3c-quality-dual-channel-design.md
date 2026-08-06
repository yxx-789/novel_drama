# V3 P3-C 设计：质量双通道（机械规则 + 可选 LLM 评审）+ 受众档位操作化

> **日期**：2026-08-06　**状态**：设计定稿（**机械规则可执行；LLM 评审只设计不执行**）　**前置**：P3-A 题材方法论、P3-B 伏笔台账

---

## 1. Goal

把质量保障从"负向单通道（LLM 一致性检查，仅写日志）"升级为**双通道**：

1. **机械规则闸门**：纯规则、零 LLM 成本，**先执行**（速度优先）。
2. **LLM 评审**：独立评审，**只出设计，暂不执行**（opt-in，默认关闭，D1）。
3. **受众档位操作化**：在 7 个受众画像之上加"注意力窗口 + 逻辑自洽取舍"两轴，落地番茄/起点式分档。

**约束**：单章生成**不新增 LLM 调用**；`check_chapter_consistency` 从 LLM 日志型改造为机械规则（或 opt-in），释放现有 1 次调用。

## 2. 现状问题（带证据）

- `check_chapter_consistency`（`task_service.py:372`）是 LLM 调用，结果仅 `logger.warning`（`"INCONSISTENT"`），**不门禁、不修复**——价值低、成本高（1 次/章）。
- 无任何"追求更好"的正向机制（无爽点校验、无伏笔对齐、无去 AI 味量化）。
- `AUDIENCE_BLOCKS` 是 7 个操作性画像（句长/爽点密度/逻辑权重/铺陈容忍/AI味避雷），但**没有"轻松/标准/精品"档位**——行业数据（澎湃/上观/36氪）显示平台差异的分水岭是"注意力窗口长度"与"逻辑自洽 vs 即时反馈的取舍"两根轴。

## 3. 设计

### 3.1 机械规则闸门（先执行，零 LLM）

新增 `backend/app/generator/quality_gates.py`，全部纯规则。**按题材取维度子集**（对齐 InkOS 26 维按题材取子集）：

| 规则 | 输入 | 输出 | 题材子集 |
|---|---|---|---|
| G1 去 AI 味限频 | 正文 | 高频词命中次数（仿佛/忽然/竟然/不禁/宛如/猛地，每 3000 字 ≤1 次） | 全题材 |
| G2 句长/短句比率 | 正文 | 平均句长 + 长句占比 vs 受众参数 | 按 audience 档位 |
| G3 段落重复 | 正文 | 相邻/同章重复短语、段落（去重后哈希） | 全题材 |
| G4 设定交叉（规则版） | 正文 + 角色卡 + 世界状态 + 伏笔台账 | 已死角色出场 / 已毁物品恢复 / 数值倒退（name 匹配 + 状态比对） | 全题材 |
| G5 字数闸门 | 正文 | draft 长度 vs `word_number` 目标（±20%） | 全题材 |
| G6 钩子存在性 | 章末 150-300 字 | 是否含四断法钩子模式（决定/发现/误判/代价关键词 + 非总结性结尾） | 非日常流题材 |
| G7 伏笔对齐 | 正文 + 台账 | 台账注入清单中该碰/该回收的伏笔是否被提及（name 匹配） | 全题材 |

**执行时机**：草稿生成后、入库前，同步执行（纯 Python，毫秒级）。输出 `{gate, severity, evidence}` 列表；**非阻塞**（只记录到 task result / 日志），供 `check_chapter_consistency` 复用与前端后续展示。

**`check_chapter_consistency` 改造**：
- 现状：LLM 调用 → `logger.warning`。
- 改为：先跑 G1-G7 机械闸门（零成本）；LLM 一致性检查从热路径移除，改为 **opt-in**（`writing_config` 开关或前端手动触发，默认关）。机械 fail 不覆盖 LLM pass（strictest merge 方向：机械 fail 优先）。

### 3.2 LLM 评审（只设计，不执行）

**设计记录（暂不实现）**：

1. **独立评审器**：独立 adapter（temperature≈0.2），与写作 agent 分离，避免"写作 agent 自我合理化"（对齐 autonovel 双免疫）。
2. **评审维度（按题材取子集）**：爽点密度、伏笔对齐、节奏张力、人设一致、叙事衔接、AI 味（对齐 QMAI 六维 + InkOS 题材子集）。输出 `{dim, score, evidence(原文引用), suggestion}`，问题分级 阻塞/高/中/低。
3. **strictest merge**：机械闸门 fail 时，LLM pass 不能覆盖（novel-architect 启发式与模型冲突取最严）。
4. **五档局部修复**（AI Fiction Studio）：只修原句 / 修这一段 / 深修此问题 / 整章轻修 / 按评审重写——默认走最小档，避免整章重写的成本与风险。
5. **触发方式**：手动 API + `writing_config` 可选自动（默认关）；前端"质量评审"按钮。
6. **成本账**：一次评审 = 1 LLM 调用/章，与现状 6 次/章相比是显著增量——这正是**缓行的原因**；机械闸门先承担大部分"找问题"职责。

### 3.3 受众档位操作化

新增 `writing_config.audience_tier`（默认"标准"，可选 `轻松 / 标准 / 精品`），加两根轴参数：

| 档位 | 注意力窗口 | 逻辑自洽 vs 即时反馈 | 叠加到 audience 画像 |
|---|---|---|---|
| 轻松（番茄式） | 极短（开篇即爽点） | 即时反馈优先 | 短句、高事件密度、章长 2000-2500、每章 1 个明确推进、伏笔短线（≤20 章回收） |
| 标准 | 中 | 平衡 | 现状 audience 画像即可 |
| 精品（起点式） | 允许长 | 逻辑自洽优先 | 可长句、允许铺垫与长线伏笔（50-100 章）、铺陈容忍提高 |

实现：在 `_prompt_context_for_project` 的 audience 片段后追加 `【受众档位·{tier}】` 分片（渲染两根轴参数）；不新增维度、不新增 LLM 调用。黄金三章按档位条件化（D5）：轻松档保留"入局→加压→承诺"，精品档允许慢热（弱化公式化开篇）。

## 4. 接口

- 新增：`quality_gates.py`（`run_quality_gates(draft, context, tier, genre) -> list[GateFinding]`，纯规则；`GateFinding = {gate, severity, evidence}`）
- 修改：`generation_service.py` / `task_service.py`——草稿生成后跑闸门（非阻塞），结果写入 task result；`check_chapter_consistency` 改机械闸门 + opt-in LLM
- 修改：`block_library.py` 或 `genre_methodology.py`——`AUDIENCE_TIER_PARAMS`（两根轴参数表）
- 修改：`project_service.py` / `schemas/project.py`——`writing_config` 新增 `audience_tier`（默认"标准"，旧项目无值回退）
- 修改：`prompts.py`——`first/next_chapter` 新增 `{audience_tier_guidance}` 占位符
- 前端：项目创建表单新增「受众档位」下拉（可选）；「质量评审」按钮（LLM 评审 opt-in 入口，本期可只显示禁用态/提示）

## 5. 兼容与降级

- 旧项目无 `audience_tier` → 默认"标准"，行为不变。
- 机械闸门全部非阻塞，任何规则异常都 try/except 跳过，不影响生成。
- `check_chapter_consistency` 改机械后，原 LLM 日志消失属预期（由闸门 findings 替代）。

## 6. 测试要点

- `test_quality_gates.py`：G1-G7 各规则的命中/未命中样例（纯规则，无 LLM，用真实句子断言）
- `test_audience_tier.py`：档位参数表三档齐全；缺省回退"标准"；prompt 片段注入生效
- 回归：`check_chapter_consistency` 改造后单章 LLM 调用数从 ≤6 降到 ≤5（机械闸门零成本）
- LLM 评审：**不实现**，只保留设计文档与接口占位（不写实现，避免被误执行）

## 7. 验收标准

- [ ] 机械闸门 G1-G7 全量生效，命中写入 task result / 日志
- [ ] 单章生成 LLM 调用数 **≤5**（consistency 改造后，比现状 6 次降低）
- [ ] 受众档位三档注入生效；黄金三章按档位条件化
- [ ] LLM 评审仅有设计文档，无执行代码，手动入口默认关闭
- [ ] 旧项目兼容回归通过
