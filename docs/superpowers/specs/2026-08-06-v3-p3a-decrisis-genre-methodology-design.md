# V3 P3-A 设计：去危机化 + 题材化伏笔/节奏方法论层

> **日期**：2026-08-06　**状态**：设计定稿　**前置**：P2-B 已按既有计划落地（本设计不依赖 P2-B 的具体实现，但与其共用 `writing_config`）

---

## 1. Goal

把生成系统从"危机形状神经"改成**按题材/结构自适应**：

1. **去危机化**：选「日常流 / 群像交织 / 单元剧」等非危机结构时，上游（种子 / 世界观 / 首章 / 目录 / 一致性）不再强制"异常征兆 / 打破平衡 / 悬念曲线 / 危机体现"。
2. **题材化方法论**：为每个题材配一套可执行的 伏笔回收间距 / 爽点频率 / 冲突驱动类型 / 钩子偏好 / 开篇弧线，注入正文 prompt。
3. **钩子形式化**：章末钩子从"悬念结尾口号"改为「四断法枚举 + 题材适配」。

**约束**：单章生成**不新增 LLM 调用**（所有注入都是 prompt 片段拼装）；旧项目（无 `writing_config`）沿用现状危机模板，行为不变。

## 2. 现状问题（带证据）

### 2.1 残留的危机形状硬规则（`backend/app/generator/prompts.py`）

| # | prompt | 行号 | 硬规则 |
|---|---|---|---|
| 1 | `core_seed_prompt` | L22-23 | 故事核心公式强制"核心事件 + 灾难后果 + 隐藏更大危机"三件套 |
| 2 | `character_dynamics_prompt` | L56-63 | 角色弧线必经"触发事件"；关系网强制"至少 2 个价值观冲突 + 1 个隐藏背叛可能性" |
| 3 | `world_building_prompt` | L90-100 | 世界观强制"断层线 / 可打破禁忌 / 资源争夺焦点 + 每维至少 3 个可互动动态元素" |
| 4 | `first_chapter_draft_prompt` | L135-139 | 首章强制"视觉符号 + 至少 2 个异常征兆 + 打破平衡事件 + 至少引入 2 个主要角色" |
| 5 | `next_chapter_draft_prompt` | L179-181 | 后续章强制"张力对比开场 + 至少推进 1 条线 + 至少 1 个角色变化"（悬念钩子 L184 已降为参考式） |
| 6 | `chapter_blueprint_prompt` | L325-355 | 目录强制"悬念密度 / 核心悬念类型 / 伏笔操作"曲线，终章前不得出现结局 |
| 7 | `architecture_consistency_prompt` | L238 | 一致性校验要求"核心种子中的危机在情节架构中得到体现" |

### 2.2 记忆系统危机形状（`world_state_templates.py` / `prompts.py` / `generation_service.py`）

- `extract_world_state_delta_prompt`（prompts.py L433-438）：只记录**变化**字段、强制事件状态迁移、期限/倒计时推进。
- `build_state_summary_prompt`（prompts.py L486-496）：摘要优先"进行中事件 / 到期倒计时 / 上 3 章内变化"，主动丢弃已完成/失败。
- `slim_state`（generation_service.py L577-602）：超限裁剪**优先保留"近期有变更历史"实体** → 静态背景最先被裁。
- 三模板均把 `events`（含 deadline/risks/stakes）设为一等追踪类。

### 2.3 默认配方危机惯性（`block_library.py` DEFAULT_RECIPES L750-859）

12 题材仅言情默认「日常流」，其余 11 类默认配方都偏冲突推进；玄幻/都市/悬疑/灵异 4 类默认「独角戏」。

## 3. 设计

### 3.1 新增模块 `backend/app/generator/genre_methodology.py`

**题材化伏笔/节奏参数表**（数据来自行业核实的方法论；12 题材全配）：

```python
GENRE_METHODOLOGY = {
    "悬疑": {
        "conflict_driver": "线索误导+真相反转；伏笔本质是认知反转（首次读为A，揭示时是B）",
        "foreshadowing_intervals": {"short": [10, 20], "mid": [30, 50], "long": [50, 100]},
        "touch_every": [20, 30],          # 长线伏笔每 20-30 章"碰一下"，不揭示但提醒存在
        "recovery_audit": True,           # 揭示真相前要求做"线索审计"：关键线索必须已出现过
        "hook_preference": ["发现", "误判"],
        "payoff_note": None,
        "opening_arc": "黄金三章递进：入局→加压→承诺（不三连爆）",
    },
    "言情": {
        "conflict_driver": "双向误会推进：先女主误会解除，再男主误会解除；'各自都对'才扎心",
        "foreshadowing_intervals": {"short": [5, 10], "mid": [15, 25], "long": [40, 60]},
        "touch_every": [8, 12],
        "recovery_audit": False,
        "hook_preference": ["决定", "误判"],
        "payoff_note": "每 2-3 章一次甜蜜互动/情感张力单元；不以事件爽点为标准，以'情绪被击中'为顶点",
        "opening_arc": "开局快抛矛盾/误会，建 CP 感",
    },
    "玄幻": {  # 含 升级/系统流 细类
        "conflict_driver": "升级循环：总目标分解为小目标（筑基→金丹→元婴），每级延伸矛盾（为筑基丹发愁）",
        "foreshadowing_intervals": {"short": [8, 15], "mid": [25, 40], "long": [60, 100]},
        "touch_every": [15, 20],
        "recovery_audit": False,
        "hook_preference": ["决定", "代价"],
        "payoff_note": "每 10 章一次大战/大突破；系统流每章至少一次签到/抽奖；小奖密集大奖稀少",
        "opening_arc": "踩泥开局→金手指→第一次小爽点",
    },
    "种田": {  # 归入 日常流 结构下的题材
        "conflict_driver": "发育变强→回报的正反馈循环；情绪主旋律是'愁'而非'危'",
        "foreshadowing_intervals": {"short": [10, 20], "mid": [30, 50], "long": [60, 90]},
        "touch_every": [15, 25],
        "recovery_audit": False,
        "hook_preference": ["决定"],
        "payoff_note": "爽点来自收获感/正反馈（春耕秋收、打脸亲戚、事业升级、全家团宠）；节奏分阶段：生存→积累→产业升级→守护传承",
        "opening_arc": "轻快进入生活流，忌沉重铺陈",
    },
    # 其余题材（仙侠/都市/科幻/奇幻/历史/武侠/灵异/军事/体育）按同类结构补全，
    # 无权威专门方法的题材（如群像）以"冲突驱动类型=功能分工推进、节奏无独立体系"作为默认值，不编造细节。
}
HOOK_FOUR_BREAKS = ["决定", "发现", "误判", "代价"]
# 决定=不可撤回的选择；发现=旧事实的新解释；误判=读者知道角色正走向错误答案；代价=目标刚达成、更大账单出现
```

关键方法：
- `get_genre_methodology(genre) -> dict`：未知题材返回 `DEFAULT_METHODOLOGY`（不报错、不降质，用通用温和值）。
- `_render_genre_methodology(genre) -> str`：把参数表渲染成 2-4 句 prompt 片段（含伏笔回收间距、爽点频率、冲突驱动类型、钩子偏好）。
- 12 题材全部有值，缺权威方法的题材用保守默认并**在注释标明出处等级**（B/C），不允许留空。

### 3.2 去危机化：structure 条件化

**方案**：`prompts.py` 的硬危机规则行替换为条件占位符；新增 `backend/app/generator/structure_guidance.py`，按 `writing_config.structure` 返回对应分片。危机驱动结构（升级打怪/三幕经典/倒叙钩子/单元剧快节奏/长线连载）保留现有关卡；非危机结构（日常流/群像交织）替换为平静/正反馈分片。

```python
# structure_guidance.py
CRISIS_STRUCTURES = {"升级打怪", "三幕经典", "倒叙钩子", "单元剧快节奏", "长线连载"}
CALM_STRUCTURES = {"日常流", "群像交织"}

def build_structure_guidance(structure: str | None) -> dict:
    """按 structure 返回 {seed, character, world, first_chapter, chapter, blueprint} 六个分片。"""
    if structure in CALM_STRUCTURES:
        return _calm_guidance()
    return _crisis_guidance()   # 现状文本，作为默认/危机结构基线
```

改造后的占位符与注入点：

| prompt | 现状硬规则 | 改为 | 注入参数 |
|---|---|---|---|
| `core_seed_prompt` | "当…必须…否则…；更大危机发酵" | `{structure_seed_guidance}`（危机/平静两版） | `build_structure_guidance(structure)["seed"]` |
| `character_dynamics_prompt` | "至少2个价值观冲突+1个隐藏背叛" | `{structure_character_guidance}`（平静版：关系可温和，弧线不强制触发事件） | `["character"]` |
| `world_building_prompt` | "断层线/禁忌/资源争夺+每维3个动态元素" | `{structure_world_guidance}`（平静版：可只追踪常态设定与稳定关系） | `["world"]` |
| `first_chapter_draft_prompt` | "至少2个异常征兆+打破平衡事件" | `{structure_first_chapter_guidance}`（平静版：日常切片+人物魅力+轻微起伏） | `["first_chapter"]` |
| `next_chapter_draft_prompt` | "张力对比开场+至少推进1条线" | `{structure_chapter_guidance}` | `["chapter"]` |
| `chapter_blueprint_prompt` | "悬念密度/悬念类型/伏笔操作曲线" | `{structure_blueprint_guidance}`（平静版：节奏分布可无悬念曲线，按题材参数） | `["blueprint"]` |
| `architecture_consistency_prompt` | "危机在架构中体现" | 改为中性："核心种子的主题/创作意图在架构中得到体现" | 直接改文本 |

平静版分片语义要点（日常流/群像交织）：
- 不强制"打破平衡"；允许章节以"人物情绪、关系变化、日常细节积累"收束。
- 冲突驱动类型改用题材参数（如种田=正反馈；群像=多线交织以事件推动关系变动）。
- 首章不强制"异常征兆"，允许"人物魅力 + 生活切片 + 一个轻微变化"。

### 3.3 题材方法论注入正文

`generate_chapter_draft` 组装时追加一个片段：

```
【题材写作方法·{genre}】
{_render_genre_methodology(genre)}
```

注入点：`first_chapter_draft_prompt` / `next_chapter_draft_prompt`（新增 `{genre_methodology}` 占位符）。**不新增 LLM 调用**——只是 prompt 里多一段话。

### 3.4 钩子形式化

`next_chapter_draft_prompt` 的"悬念钩子"参考式（L184）升级为：

```
【章末钩子】
如本章收束时需要钩子，请在下列四类中选择与题材最匹配的一种（{hook_preference} 优先）：
- 决定：主角做了一个不可撤回的选择
- 发现：对旧事实的一个新解释
- 误判：读者知道角色正走向错误答案
- 代价：目标刚达成，更大账单出现
断在变化发生的那一刻，不要在章尾总结。
```

由 `_render_genre_methodology` 输出 `hook_preference` 列表；`generate_chapter_draft` 注入。

### 3.5 记忆中性化（阶段 2 范围内的轻量项）

不改 schema、不加调用，只改两个 prompt 的**描述性约束**：

- `extract_world_state_delta_prompt`：追加"除变化外，保留对后续章节仍有意义的关键常态状态（主角核心身份、稳定关系、重要场所），不要当作变化丢弃"。当 structure 为平静结构时生效（传参控制）。
- `build_state_summary_prompt`：追加"若为非危机驱动结构，摘要应同时保留当前'舒适/日常状态'与情绪基调，而非只保留事件与倒计时"。
- `slim_state` 裁剪逻辑：平静结构下保留"稳定关系/常态状态"条目（按题材参数判定是否启用，规则简单，不新增 LLM）。

> 记忆系统彻底改造（分层冻结/台账）放阶段 3；此处只做"描述性去危机"，避免阶段 2 改动面过大。

## 4. 接口

- 新增：`genre_methodology.py`（`get_genre_methodology` / `_render_genre_methodology` / `HOOK_FOUR_BREAKS` / `DEFAULT_METHODOLOGY`）
- 新增：`structure_guidance.py`（`build_structure_guidance(structure) -> dict`，含 6 键分片）
- 修改：`prompts.py`（7 处硬规则 → 条件占位符 / 中性文本；`first/next_chapter` 新增 `{genre_methodology}`、`{structure_*_guidance}` 占位符）
- 修改：`generation_service.py`（`generate_chapter_draft` / `generate_architecture` / `generate_directory` 组装时计算并传入新占位符；`_prompt_context_for_project` 读取 structure）
- 修改：`task_service.py`（如需把 structure 传入各生成函数；旧项目无 writing_config → `build_structure_guidance(None)` 返回危机基线，行为不变）

## 5. 兼容与降级

- 旧项目（无 `writing_config` 或 structure 缺省）：`build_structure_guidance(None)` → 危机基线（现状文本），**生成行为与改造前一致**。
- 未知题材：`get_genre_methodology` 返回 `DEFAULT_METHODOLOGY`，不报错。
- 前端无需改动（参数都从既有 `writing_config` 读）。

## 6. 测试要点

- `test_genre_methodology.py`：12 题材参数表非空、渲染片段含伏笔间距/爽点频率；未知题材回退默认。
- `test_structure_guidance.py`：6 结构分类正确（危机/平静）；`None`/缺省回退危机基线；6 分片键齐全。
- `test_prompts.py` 补：`first/next_chapter` format 时新占位符有值；一致性 prompt 不再含"危机体现"。
- 旧项目回退回归：无 writing_config 生成章节，产出与改造前 diff 无结构性差异（抽查 1-2 章）。

## 7. 验收标准

- [ ] 日常流/群像交织项目：章节正文不再出现"异常征兆/打破平衡事件/悬念曲线"硬规则痕迹。
- [ ] 升级打怪/悬疑项目：保留危机推进与悬念。
- [ ] 题材参数表 12 题材全有值；抽查 ≥2 题材正文的伏笔回收间距/爽点频率与参数匹配。
- [ ] 章末钩子按题材偏好落在四断法之一。
- [ ] 单章生成 LLM 调用数不变（仍 ≤6，阶段 2 不增）。
- [ ] 旧项目生成行为不变（回退回归通过）。
