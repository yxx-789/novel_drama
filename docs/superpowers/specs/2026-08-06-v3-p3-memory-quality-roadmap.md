# V3 P3 记忆与质量深化 · 路线图

> **日期**：2026-08-06
> **状态**：设计定稿，按阶段执行
> **前置**：V3 P1（积木库/减法/创作意图/冲突规则）已完成；P2-A（结构化章节记忆）已完成；**P2-B（角色卡）按既有 spec/plan 先行执行**，本路线图假定 P2-B 已落地。

---

## 1. 目标与约束

- **首要目标**：整体提升生成质量（长线一致性 / 题材适配 / 去 AI 味 / 去危机化）。
- **兼顾速度**：**单章生成不新增 LLM 调用**。LLM 评审只出设计方案、暂不执行（opt-in，默认关闭）。
- 不破坏既有功能（生成 / 记忆 / 短剧 / 导出 / AI 问答）；旧项目（无 `writing_config` / 旧文本角色）兼容降级。
- 文案不出现「小红书」。

## 2. 现状基线（为什么这样分阶段）

**单章生成当前最多 6 次 LLM 调用**（`task_service.py` `run_chapter_task` / `run_batch_chapters_task`）：

| # | 调用 | 位置 | 是否阻塞 |
|---|---|---|---|
| 1 | `build_state_summary`（世界状态摘要） | task_service:344 | 非阻塞 try/except |
| 2 | `generate_chapter_draft`（正文） | task_service:355 | **阻塞（主产物）** |
| 3 | `check_chapter_consistency`（一致性检查） | task_service:372 | 非阻塞，**仅写日志** |
| 4 | `update_character_state`（角色状态更新） | task_service:390 | 非阻塞 |
| 5 | `extract_world_state_delta`（世界状态增量） | task_service:401 | 非阻塞 |
| 6 | `extract_chapter_memory`（结构化章节记忆） | task_service:450 | 非阻塞 |

速度结论：
- 真正的产物调用只有 1 次；其余 5 次都是记忆/校验的**旁路 LLM 调用**。
- `check_chapter_consistency` 是**纯日志型**负向校验（`"INCONSISTENT"` 仅 `logger.warning`），对产品价值最低 → **阶段 4 第一个改造对象**（机械规则替换，零 LLM 成本，或改 opt-in）。
- 任何"新增 LLM 评审"都会加重第 3 次调用——故 **LLM 评审必须 opt-in、默认关闭**（决策 D1）。

**缺陷根因与阶段对应**（详见《V3 系统体检报告》缺陷清单 A-G）：

| 缺陷 | 根因 | 由谁解决 |
|---|---|---|
| A 危机形状深入上游（结构单一） | seed/world/first_chapter/blueprint/consistency 仍强制危机 | **阶段 2** |
| B 角色数量受限（角色少） | 默认配方独角戏 + cast_scale 位置劣势 + 样例锚定 | 阶段 2（部分）+ P2-B |
| C 记忆无分层、无伏笔台账（长线稀释） | actual_summary_json 逐章覆盖；无台账 | **阶段 3** |
| D 质量保障负向单通道 | 只有"找问题"，无"追求更好" | **阶段 4** |
| E 去 AI 味缺量化 | 只有定性避雷 | **阶段 4** |
| F 题材化伏笔/节奏方法论缺失 | 只有一句「伏笔手法倾向」 | **阶段 2** |
| G 受众档位未操作化 | 7 画像无"注意力窗口/逻辑自洽取舍"两轴 | **阶段 4** |

## 3. 阶段划分与依赖

| 阶段 | 代号 | 内容 | 解缺陷 | 状态 |
|---|---|---|---|---|
| 1 | P2-B | 角色卡（characters 资产 JSON 化 + 双通道兼容） | B、角色一致性 | 既有 spec/plan，**先行执行** |
| 2 | P3-A | 去危机化（structure 条件化）+ 题材伏笔/节奏方法论层 + 钩子四断法 | A、F | **已实现**（P3-A：`genre_methodology.py` + `structure_guidance.py` + 接线 + 记忆中性化；单章 LLM 调用数不变） |
| 3 | P3-B | 记忆分层（arc 级摘要冻结 + 实体档案加载）+ 伏笔台账/副线提醒 | C | 设计定稿，执行待定 |
| 4 | P3-C | 质量双通道（机械规则先执行 + LLM 评审只设计）+ 受众档位操作化 | D、E、G | 设计定稿，机械规则可执行 |

**依赖**：
- 阶段 2 的题材参数表独立于阶段 3，可并行设计/执行。
- 阶段 3 的伏笔台账复用 P2-B 角色卡；台账更新**不新增 LLM 调用**（扩展现有 `extract_chapter_memory` 的输出字段）。
- 阶段 4 机械规则依赖阶段 3 的台账做"伏笔逾期/未回收"类检查。

## 4. 关键决策记录

- **D1（LLM 评审：设计不执行）**——首要目标质量+速度。LLM 评审设计成 opt-in、默认关闭；机械规则闸门先执行（零 LLM 成本）。现有 `check_chapter_consistency` 从 LLM 日志型改造为机械规则或 opt-in。
- **D2（题材参数独立模块）**——伏笔/节奏参数表用独立模块 `genre_methodology.py`（正交、可测、可扩展），不内联进 `prompts.py`。
- **D3（known_by 事实级放阶段 3）**——P2-B 角色卡 schema 先行不扩；「事实级 known_by + 三态认知（知道/不知道/读者知道角色不知道）」放阶段 3 的伏笔/事实台账层实现（粒度对齐 `facts.jsonl`）。
- **D4（钩子形式化）**——章末钩子从"悬念结尾口号"改为「四断法枚举：决定 / 发现 / 误判 / 代价 + 题材适配偏好」。
- **D5（黄金三章条件化）**——「入局→加压→承诺」作为开篇验收，按受众档位条件化；行业明确有争议，不当作金科玉律。

## 5. 前沿借鉴映射表（全部核实，非编造）

| 机制 | 来源（已核实） | 落点 |
|---|---|---|
| 题材→伏笔回收间距/爽点频率/冲突驱动类型 | 中文行业（马良写作/360doc/知乎，B-A 级） | 阶段 2 `genre_methodology.py` |
| 钩子四断法（决定/发现/误判/代价） | 马良写作《黄金三章检查》 | 阶段 2 章末钩子 |
| 六层摘要冻结 L0-L5 | long-novel-writer | 阶段 3 记忆分层（适配为 L1 章/L2 arc/L3 全书） |
| 实体档案只加载出场实体 | long-novel-writer（写前 25-40k token） | 阶段 3 + P2-B active characters |
| 事实级 known_by + 三态认知 | QMAI / long-novel-writer | 阶段 3 台账 |
| 副线闲置 >N 章提醒 | long-novel-writer / InkOS subplot_board | 阶段 3 台账 |
| 读者承诺账本（引入/兑现/逾期/未闭合） | novel-architect | 阶段 3 台账 |
| 量化去 AI 味限频（每 3000 字 ≤1 次） | InkOS | 阶段 4 机械规则 |
| 双免疫质量闸门 + strictest merge | novel-architect / autonovel | 阶段 4（机械执行，LLM opt-in） |
| 题材专属审计维度子集 | InkOS 26 维按题材取子集 | 阶段 4 机械规则维度表 |
| 五档局部修复 | AI Fiction Studio | 阶段 4 修复设计（延后） |
| 节拍竞争（写前比更强候选桥段） | novel-architect | 阶段 4 设计（延后） |
| 番茄 vs 起点档位（注意力窗口/逻辑自洽取舍） | 澎湃/上观/36氪（A 级数据） | 阶段 4 受众档位 |

## 6. 每阶段验收标准

- **阶段 1（P2-B）**：按既有 spec/plan 验收（角色卡 JSON 读写、旧文本兼容、drama/导出/前端回归）。
- **阶段 2（P3-A）**：
  - 选「日常流 / 种田 / 群像交织」的项目，生成章节不再出现"异常征兆 + 打破平衡事件 + 悬念曲线"硬规则；选「升级打怪 / 悬疑」的项目保留危机推进。
  - 题材参数表对全部 12 题材有值；注入正文 prompt 后 LLM 伏笔回收间距/爽点频率与题材匹配（抽查 ≥2 题材）。
  - 章末钩子按题材偏好落在四断法之一。
  - 旧项目（无 writing_config）生成行为与改造前一致。
- **阶段 3（P3-B）**：arc 摘要冻结后，早期细节不再被逐章覆盖稀释（抽查 30 章 + 项目的 arc 摘要仍保留前 10 章关键事件）；伏笔台账逐章更新且无新增 LLM 调用；副线闲置 >20 章在写前上下文出现提醒。
- **阶段 4（P3-C）**：机械规则全量生效且单章生成 **LLM 调用数不增**；`check_chapter_consistency` 改造后不占 LLM；去 AI 味限频命中率可测；LLM 评审设计文档就绪、默认关闭、手动可触发。

## 7. 参考文档

- 体检报告（缺陷清单 A-G 出处）
- `docs/superpowers/specs/2026-08-06-v3-p2b-character-cards-design.md` / `plans/2026-08-06-v3-p2b-character-cards.md`
- 阶段 2：`docs/superpowers/specs/2026-08-06-v3-p3a-decrisis-genre-methodology-design.md` + plan
- 阶段 3：`docs/superpowers/specs/2026-08-06-v3-p3b-memory-layering-ledger-design.md`
- 阶段 4：`docs/superpowers/specs/2026-08-06-v3-p3c-quality-dual-channel-design.md`
