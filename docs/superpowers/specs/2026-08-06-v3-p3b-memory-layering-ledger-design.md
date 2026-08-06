# V3 P3-B 设计：记忆分层 + 伏笔台账

> **日期**：2026-08-06　**状态**：设计定稿（执行待定，阶段 2 之后）　**前置**：P2-B 角色卡、P3-A 题材方法论

---

## 1. Goal

解决「长线稀释」与「伏笔/副线丢失」两个行业公认第一大痛点：

1. **记忆分层**：`actual_summary_json` 目前逐章覆盖，早期细节被"摘要的摘要"稀释。引入 arc 级（每 N 章）与全书级摘要，**写定后冻结**，写入前按优先级组装。
2. **伏笔台账**：把散落在每章 `foreshadowing_added` 的伏笔收敛成一本台账，追踪 触碰/回收/逾期，写前注入"该碰的伏笔 / 该回收的伏笔"。
3. **副线闲置提醒**：台账带副线标记，闲置超 N 章在写前上下文提醒。

**约束**：单章生成**不新增 LLM 调用**——台账更新复用现有 `extract_chapter_memory` 调用（扩展输出字段）；arc 摘要只在 arc 边界触发（摊薄 1/N 次/章，不在逐章热路径）。实体加载复用 P2-B 的 active-character 机制，避免上下文爆炸。

## 2. 现状问题（带证据）

- `Chapter.actual_summary_json`（`task_service.py:450/656` 写入）逐章覆盖：第 30 章的摘要只代表"第 30 章发生了什么"，前 10 章关键事件已不在上下文。
- `extract_chapter_memory_prompt` 输出 `foreshadowing_added: [{name, note}]`，但**无人追踪后续**：不触碰、不回收、不逾期——伏笔静默丢失。
- 写前读入**全量**角色状态 + 全量世界状态（`task_service.py` 读取 characters 全文 + world_state），角色一多即膨胀，反向压制群像。

## 3. 设计

### 3.1 记忆分层（无新增表，存 ProjectAsset.content_json）

| 层 | 内容 | 存储 | 冻结 |
|---|---|---|---|
| L1 | 单章实际摘要（现有） | `Chapter.actual_summary_json` | 逐章覆盖（现状，不变） |
| L2 | **arc 摘要**：每 N 章一段（默认 N=15，可配） | 新资产 `arc_summaries`：`{arcs: [{arc_index, chapter_range, title, summary, frozen_at}], book_summary: {...}}` | **arc 完成后冻结，不被后续 arc 覆盖** |
| L3 | 全书摘要：由已冻结的 arc 摘要合成 | 同上 `book_summary` | arc 每完成后增量刷新 |

**arc 摘要生成时机**：仅当 `chapter_num % ARC_SIZE == 0`（arc 边界）触发一次 `build_arc_summary` LLM 调用，输入=本 arc 各章的 `actual_summary_json`（已提取，无需重读正文）。摊薄成本 = 1/N 次/章，**不在逐章热路径**。全书写完时用各 arc 摘要合成 book_summary（1 次调用）。

**写前上下文组装优先级**（对齐 QMAI 11 级思想，适配本项目）：
```
当前 arc 摘要（L2，若存在） > 上一章 actual_summary_json.summary（L1） > 上一章正文结尾（_chapter_excerpt）> 全书摘要（L3，抽查引用）
```
`task_service` 的 `previous_chapter_summary` 目前只用 L1；阶段 3 在 arc 边界后把 L2 追加进上下文（`world_state_summary` 或独立占位符），L3 仅在有引用需要时注入（避免长期占 token）。

### 3.2 伏笔台账（零新增 LLM 调用）

**新资产 `foreshadowing`（ProjectAsset.content_json）**：

```json
{
  "entries": [
    {
      "id": "uuid 或 hash(name+added_chapter)",
      "name": "伏笔名",
      "note": "埋设说明",
      "added_chapter": 3,
      "last_touch_chapter": 3,
      "planned_recovery_range": [30, 50],   // 由题材参数表 foreshadowing_intervals 给区间
      "status": "open | touched | recovered | abandoned",
      "subplot": false,                      // 是否为副线（>1 章持续推进的支线）
      "known_by": ["主角"],                   // 事实级 known_by：谁知道这条伏笔/信息
      "tags": []
    }
  ]
}
```

**更新源**：扩展 `extract_chapter_memory_prompt` 输出（同一 LLM 调用，不新增）：

```json
{
  "summary": "...", "hook": "...", "characters": [...], "relations_changed": {...},
  "foreshadowing_added": [{"name": "伏笔名", "note": "埋设说明", "known_by": ["角色"]}],
  "foreshadowing_touched": ["伏笔名"],      // 本章推进/提及了既有伏笔
  "foreshadowing_recovered": ["伏笔名"],    // 本章回收了既有伏笔
  "subplot_advanced": ["副线名"],           // 本章推进了哪条副线
  "connects_to": "..."
}
```

**台账合并（纯规则，无 LLM）**：
- `foreshadowing_added` → 新增 entry（`status=open`，`planned_recovery_range` 按题材参数表取）
- `foreshadowing_touched` → 匹配 name 设 `status=touched`、更新 `last_touch_chapter`、合并 `known_by`
- `foreshadowing_recovered` → 匹配 name 设 `status=recovered`
- 匹配失败（LLM 命名漂移）→ 保留到 `unmatched` 数组，人工/后续章节再合并，不静默丢弃

**写前注入（纯规则）**：
- 逾期未碰：`current_chapter - last_touch_chapter > touch_every[1]` 的 open/touched 伏笔 → 注入"该碰一下"清单
- 进入回收窗口：`current_chapter ∈ planned_recovery_range` 且未回收 → 注入"该考虑回收"清单
- 副线闲置：`subplot=true` 且 `current_chapter - last_touch_chapter > 20` → 注入"这条副线已闲置 N 章"提醒

### 3.3 实体档案只加载出场实体（上下文控制）

P2-B 已实现 `load_active_character_cards`（按 `known_by`/`last_appearance` 加载出场角色）。阶段 3 扩展：
- 角色卡按出场加载已有；新增按 **伏笔台账** 加载"与当前章节相关的伏笔"（写前注入用，见上）。
- 世界状态 slim 已限 10 条/类；阶段 3 保持，不再全量注入。
- 全书摘要（L3）只在需要引用历史细节时注入（如伏笔回收、call-back），避免常驻 token。

### 3.4 信息不对称：事实级 known_by + 三态认知

- **本阶段落地**：伏笔台账每 entry 带 `known_by`（谁知晓该伏笔/秘密）——直接支持"角色用了不该知道的信息"类 OOC 拦截（对齐 QMAI 三态中"角色不知道"的一面）。
- **三态扩展（设计记录，后续）**：`known_by`（角色知道）/ `hidden_from`（角色不知道但读者可能知道）/ `reader_knows_but_character_does_not`。本阶段实现前两态；第三态留给需要"读者视角制造悬念"的场景（阶段 4 钩子/悬念题材用）。
- 角色卡 `known_by` 不再复制到角色级——**事实在台账，角色卡只存引用/最近出场**，避免双写不一致（D3）。

## 4. 接口

- 修改 `prompts.py`：`chapter_memory_extract_prompt` 扩展 `foreshadowing_touched/recovered` + `subplot_advanced` + `foreshadowing_added.known_by`
- 修改 `generation_service.py`：`extract_chapter_memory` 解析新字段；新增 `build_arc_summary(chapters, llm_config)`（arc 边界调用）；新增 `synthesize_book_summary(arcs, llm_config)`
- 新增 `foreshadowing_ledger.py`：`merge_foreshadowing_delta(ledger, memory, genre, chapter_num) -> ledger`（纯规则）；`build_foreshadowing_reminder(ledger, current_chapter, methodology) -> str`（纯规则）
- 修改 `task_service.py`：arc 边界触发 arc 摘要；写前组装 L1/L2；台账合并与提醒注入
- 数据：`ProjectAsset.asset_type` 白名单新增 `arc_summaries` / `foreshadowing`（`routers/assets.py` ASSET_TYPES）

## 5. 兼容与降级

- 旧项目无 `arc_summaries` / `foreshadowing` 资产 → 自动初始化空结构，行为回退现状（只用 L1）。
- `extract_chapter_memory` 新字段缺失（旧 LLM 输出）→ 解析时容忍缺失，台账合并跳过空字段。
- 前端暂不展示台账（阶段 3 聚焦后端），不破坏既有 Tab。

## 6. 测试要点

- `test_foreshadowing_ledger.py`：新增/触碰/回收/逾期状态迁移（纯规则单测，无 LLM）；命名漂移进 unmatched；known_by 合并
- `test_arc_summary.py`：arc 边界触发、冻结不覆盖、L3 合成
- 回归：旧项目（无新资产）生成行为不变；`extract_chapter_memory` 旧格式解析容错
- **LLM 调用数断言**：单章（非 arc 边界）LLM 调用数 = 现状 ≤6；arc 边界 = ≤7（含 arc 摘要，摊薄 1/N）

## 7. 验收标准

- [ ] 30 章 + 项目：arc 摘要仍保留前 10 章关键事件（不被逐章覆盖稀释）
- [ ] 伏笔台账逐章更新，逾期/待回收/副线闲置在写前上下文出现
- [ ] 单章 LLM 调用数不变（非边界 ≤6）
- [ ] 旧项目兼容回归通过
