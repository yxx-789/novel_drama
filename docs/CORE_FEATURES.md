# 核心功能技术实现思路

> 本文档详细阐述"AI 小说 & 短剧创作工作台"两大核心引擎的设计哲学、实现思路与技术壁垒。
>
> 目标读者：技术合伙人、投资人、高级工程师

---

## 目录

1. [设计哲学：为什么不是简单的 GPT 套壳](#1-设计哲学为什么不是简单的-gpt-套壳)
2. [小说生成引擎](#2-小说生成引擎)
   - 2.1 雪花递进式架构生成
   - 2.2 悬念节奏驱动的目录设计
   - 2.3 上下文感知的章节生成
   - 2.4 一致性闭环：生成 → 校验 → 修正
3. [短剧改编引擎](#3-短剧改编引擎)
   - 3.1 从小说到剧本的映射范式
   - 3.2 导演级分镜脚本生成
   - 3.3 续集记忆机制
4. [世界状态系统：核心壁垒](#4-世界状态系统核心壁垒)
   - 4.1 问题定义：AI 长篇写作的致命伤
   - 4.2 Genre-aware 状态追踪
   - 4.3 Delta 提取与合并
   - 4.4 状态摘要注入
5. [Prompt 工程体系](#5-prompt-工程体系)
6. [数据流转全景图](#6-数据流转全景图)

---

## 1. 设计哲学：为什么不是简单的 GPT 套壳

### 1.1 行业现状的问题

市面上的 AI 写作工具普遍存在三个致命缺陷：

| 缺陷 | 表现 | 后果 |
|------|------|------|
| **单点生成** | 只能生成一段文字，无法维持长篇连贯性 | 写第 10 章时，主角的能力、物品、关系已经和第 1 章矛盾 |
| **无结构输出** | 输出的是"文章"而非"可操作的创作资产" | 编剧拿到后还要手动拆解成角色列表、场景清单 |
| **无改编能力** | 小说和剧本是两个完全独立的流程 | 编剧需要重新阅读小说、手动提取情节、重新创作 |

### 1.2 我们的核心假设

**假设一：长篇小说生成是一个"状态机"问题，而非"文本续写"问题**

GPT 擅长写下一句话，但小说创作需要的是维护一个不断演进的世界状态（谁在什么地方、有什么能力、和谁是什么关系）。我们把生成问题重新定义为：**维护一个结构化状态机，然后让 AI 基于当前状态生成下一章**。

**假设二：短剧改编不是"摘要"，而是"映射式重构"**

小说到短剧不是缩短字数，而是改变叙事媒介（文字 → 视听）。需要：
- 心理描写 → 视觉动作
- 环境描写 → 运镜和音效
- 长对话 → 短台词 + 表情特写

**假设三：创作是一个迭代过程，不是一次性生成**

用户需要：生成 → 编辑 → 再生成 → 再编辑。系统必须支持增量更新和版本回溯。

---

## 2. 小说生成引擎

### 2.1 雪花递进式架构生成

**核心思路：从抽象到具体，五步递进，每步基于前一步的输出**

传统的一次性 Prompt："请为我写一部修仙小说的架构" → AI 输出 5000 字，但角色和世界观可能矛盾。

我们的雪花递进法：

```
Step 1: Core Seed（核心种子）
    输入：主题 + 类型 + 篇幅
    输出：一句话故事公式
    示例："当废柴少年意外获得上古剑灵，必须在宗门大比中证明自己，否则将被逐出师门；
           与此同时，一个针对整个修仙界的阴谋正在暗处发酵。"
    
    作用：确定故事的"DNA"，后续所有生成必须与此一致

Step 2: Character Dynamics（角色动力学）
    输入：Core Seed
    输出：3-6 个核心角色的完整档案
    
    每个角色包含：
    - 基础特征（背景、外貌、职业）
    - 驱动力三角：表面追求 / 深层渴望 / 灵魂需求
    - 角色弧线：初始状态 → 触发事件 → 认知失调 → 蜕变节点 → 最终状态
    - 关系冲突网：合作纽带 + 隐藏背叛可能性
    
    作用：确保角色有"变化潜力"，不是静态人设

Step 3: World Building（世界构建）
    输入：Core Seed
    输出：三维交织的世界观
    
    三个维度：
    - 物理维度：空间结构、时间轴、法则体系（及漏洞点）
    - 社会维度：权力断层线、文化禁忌、经济命脉
    - 隐喻维度：视觉符号系统、气候映射心理、建筑暗示文明
    
    要求：每个维度至少 3 个可与角色决策互动的动态元素
    作用：世界观不是背景板，而是推动情节的"活性系统"

Step 4: Plot Architecture（情节架构）
    输入：Core Seed + Character Dynamics + World Building
    输出：三幕式悬念结构
    
    第一幕（触发）：日常异常 → 关键事件 → 错误抉择
    第二幕（对抗）：剧情升级 → 双重压力 → 虚假胜利 → 灵魂黑夜
    第三幕（解决）：代价显现 → 嵌套转折（三层认知颠覆）→ 余波悬念
    
    每个阶段包含：3 个关键转折点 + 对应的伏笔回收方案
    作用：确保故事有"认知过山车"式的阅读体验

Step 5: Architecture Consistency Check（一致性校验）
    输入：前 4 步的全部输出
    输出：一致性报告
    
    校验维度：
    - 角色设定是否前后一致
    - 世界观与情节是否矛盾
    - 核心种子与情节走向是否一致
    - 角色动机与行为是否一致
    
    如果发现矛盾，输出具体矛盾描述，供人工修正或自动重试
```

**为什么用雪花法而非单步生成？**

| 维度 | 单步生成 | 雪花递进 |
|------|---------|---------|
| 一致性 | 角色和世界观可能矛盾 | 每步验证前一步，矛盾概率极低 |
| 可控性 | 黑盒，无法干预中间过程 | 每步输出可人工编辑后再进入下一步 |
| 质量 | 平均 | 每步专注一个维度，深度更好 |
| 可解释性 | 不知道为什么会这样 | 可追溯每个设计决策的依赖链 |

### 2.2 悬念节奏驱动的目录设计

**核心思路：目录不是"章节列表"，而是"悬念曲线的设计图"**

传统目录：第 1 章 初入宗门 / 第 2 章 修炼开始 / 第 3 章 遭遇挫折...

我们的目录：每章包含 6 个维度的设计意图：

```
第 5 章 - 暗流涌动
本章定位：事件 / 副线推进
核心作用：推进（主线交叉点）
悬念密度：渐进
伏笔操作：埋设(A线索) → 强化(B矛盾)
认知颠覆：★★☆☆☆
本章简述：宗门大比前夕，主角发现裁判长老与敌对势力秘密会面
```

**章节集群设计**：

- 每 3-5 章构成一个"悬念单元"，包含完整的小高潮
- 单元之间设置"认知过山车"：连续 2 章紧张 → 1 章缓冲
- 关键转折章预留多视角铺垫

**生成策略**：

```
输入：小说架构（5 步输出）+ 目标章节数
输出：N 章目录，每章含 6 维度设计

约束：
- 在生成目标章节数前不出现结局章节
- 悬念曲线必须呈"上升-缓冲-爆发"的周期性波动
- 伏笔必须有埋设、强化、回收的完整生命周期
```

### 2.3 上下文感知的章节生成

**核心问题：第 N 章生成时，AI 需要知道什么？**

传统做法：只给"小说设定"和"本章标题" → AI 自由发挥 → 前后矛盾。

我们的上下文注入：

```
第 N 章 Prompt 的上下文构成：

【小说设定】        ← 来自 Step 1-4 的架构输出（静态，全剧不变）
【角色状态】        ← 截至第 N-1 章的最新角色状态文档（动态，每章更新）
【世界状态摘要】    ← 从 world_state 中提取的 5-10 条最相关状态（动态）
【前一章概要】      ← 第 N-1 章的故事摘要（确保情节连贯）
【前一章结尾片段】  ← 第 N-1 章最后 500 字（确保文风连贯）
【本章信息】        ← 目录中本章的 6 维度设计意图
```

**关键设计：第 1 章 vs 后续章节的差异化 Prompt**

- **第 1 章**：专注"开篇仪式"——视觉符号引入、日常状态展示、异常征兆埋伏、打破平衡事件
- **后续章节**：专注"张力对比"——情感/情节张力切换、主线推进、角色变化、悬念钩子

**字数控制**：

Prompt 中明确指定"预计字数"，LLM 的输出长度与指定字数误差控制在 ±15% 以内。通过 `max_tokens` 参数和 Prompt 中的字数要求双重约束。

### 2.4 一致性闭环：生成 → 校验 → 修正

**问题：即使注入了上下文，LLM 仍可能"幻觉"出矛盾内容。**

我们的三层校验机制：

**Layer 1: 生成时约束（Prompt 内）**

```
Prompt 中明确写入：
"必须严格遵循【世界状态摘要】中的所有设定，禁止出现与摘要矛盾的情节
（如已死亡角色出场、已损坏物品完好、境界/能力倒退等）。
若摘要中标记某角色'已死亡'，则本章不得安排其出场（回忆/梦境除外）。"
```

**Layer 2: 生成后校验（LLM 自检）**

```
生成完成后，系统自动发起第二次 LLM 调用：

输入：【角色状态】+【前一章结尾】+【待审查章节】
任务：检查角色一致性、情节一致性、世界观一致性
输出：CHECK: CONSISTENT 或 CHECK: INCONSISTENT + 矛盾列表

如果发现矛盾：
- 记录到任务日志
- 继续生成（不阻塞），但标记警告
- 用户可在编辑界面看到一致性提示
```

**Layer 3: 角色状态自动更新（世界状态系统）**

```
章节生成后：
1. 用 LLM 提取本章的角色/事件/世界变更（Delta）
2. 合并到 world_state
3. 更新 character_state 文档
4. 下一章生成时自动使用更新后的状态
```

---

## 3. 短剧改编引擎

### 3.1 从小说到剧本的映射范式

**核心洞察：短剧不是小说的"缩短版"，而是"视听重构版"**

| 小说叙事 | 短剧叙事 | 转换规则 |
|---------|---------|---------|
| "他心里很紧张" | 特写：手指颤抖，额头冒汗 | 心理 → 视觉 |
| "房间很破旧" | 全景：斑驳墙壁，摇晃的灯泡 | 描述 → 运镜 |
| 500 字对话 | 3 句台词 + 眼神交流 | 长对话 → 短台词 + 表情 |
| 内心独白 | 沉默 + 背景音乐渐强 | 独白 → 音效 |
| 时间推移 | 蒙太奇：日历翻页 + 季节变化 | 叙述 → 剪辑 |

**改编流程**：

```
Step 1: 改编计划生成
    输入：小说架构 + 选定章节
    输出：每集的 {hook, story_beats, cliffhanger, key_items}
    
    关键设计：
    - 每集基于 2-4 章小说内容
    - 每集必须有独立钩子（前 3 秒抓住观众）
    - 每集结尾必须有 cliffhanger（促使点击下一集）
    - key_items 用于跨集 continuity（关键道具不能丢）

Step 2: 分集脚本生成
    输入：单集大纲 + 对应章节原文 + 前集脚本（续集记忆）
    输出：导演级分镜脚本（JSON 结构化）
```

### 3.2 导演级分镜脚本生成

**输出格式不是文本，而是结构化 JSON**：

```json
{
  "episode_num": 1,
  "title": "暗流涌动",
  "scenes": [
    {
      "scene_num": 1,
      "source_chapter_range": "第 1-2 章",
      "mapped_beat_num": 1,
      "location": "宗门广场",
      "time": "清晨",
      "interior_exterior": "外",
      "characters": ["主角", "大师兄"],
      "mood": "压抑",
      "shots": [
        {
          "shot_num": 1,
          "type": "全景",
          "duration": "3秒",
          "visual": "雾气弥漫的广场，弟子们三三两两",
          "action": "主角独自站在角落，手握断剑",
          "dialogue": {
            "speaker": "大师兄",
            "content": "你还来做什么？",
            "emotion": "轻蔑"
          },
          "camera_movement": "缓慢推进",
          "audio": {
            "bgm": "低沉弦乐",
            "sfx": ["风声", "远处钟鸣"]
          }
        }
      ]
    }
  ],
  "adaptation_notes": "场景1改编自第1章开头...",
  "key_items": ["断剑", "神秘玉佩"]
}
```

**为什么用 JSON 而非文本？**

1. **可直接对接拍摄**：导摄团队可以按 scene/shot 分解任务
2. **可计算**：统计总镜头数、总时长、角色出场次数
3. **可版本控制**：diff 清晰，知道改了哪一场戏
4. **可渲染**：前端可直接渲染为分镜预览图

**生成约束（Prompt 内强制要求）**：

- 每个 beat 必须有对应的场景和镜头（不能跳过）
- 关键道具必须在剧本中体现（不能丢失）
- 场景数控制在 6-8 个，镜头数 20-40 个（适配竖屏短剧时长）
- 每个镜头时长 1-6 秒
- 台词要短、狠、符合人设（竖屏观众的注意力窗口很短）
- 必须标注 source_chapter_range 和 mapped_beat_num（可追溯）

### 3.3 续集记忆机制

**问题：第 N 集的编剧不知道第 N-1 集结尾发生了什么 → 剧情断裂**

**解决方案：自动提取前集关键信息注入 Prompt**

```python
def build_context_summary(prev_scripts: list[dict]) -> str:
    """从前几集脚本中提取关键信息，生成前情提要"""
    lines = []
    for script in prev_scripts[-3:]:  # 只取最近 3 集
        ep_num = script.get("episode_num", "?")
        title = script.get("title", "未命名")
        key_items = script.get("key_items", [])
        
        # 提取最后一幕的结尾台词（cliffhanger）
        scenes = script.get("scenes", [])
        cliffhanger = ""
        if scenes:
            last_scene = scenes[-1]
            shots = last_scene.get("shots", [])
            if shots:
                last_shot = shots[-1]
                dialogue = last_shot.get("dialogue", {})
                if dialogue:
                    cliffhanger = f"最后台词：{dialogue.get('speaker', '?')}「{dialogue.get('content', '')}」"
        
        lines.append(f"第{ep_num}集《{title}》：关键道具 {key_items}；{cliffhanger}")
    
    return "\n".join(lines)
```

注入位置：生成第 N 集脚本时，Prompt 开头就是前情提要，确保 AI 知道：
- 上一集结尾发生了什么
- 哪些关键道具需要延续
- 哪些悬念需要回应

---

## 4. 世界状态系统：核心壁垒

### 4.1 问题定义：AI 长篇写作的致命伤

**现象**：GPT-4 写一篇 5000 字短篇没问题，但写 50 章长篇小说时，第 30 章会把第 5 章写死的角色拉出来打酱油。

**根因**：LLM 的上下文窗口有限（即使 128K token，在长篇中也是"近大远小"——对最近内容记忆清晰，对久远内容模糊）。

**行业现状的应对方案（都不够好）**：

| 方案 | 问题 |
|------|------|
| RAG（向量检索） | 检索的是"相似文本"，不是"结构化状态" |
| 全文摘要 | 太长则丢细节，太短则丢关键信息 |
| 人工维护角色表 | 用户负担重，容易遗漏 |

**我们的方案：结构化世界状态追踪**

### 4.2 Genre-aware 状态追踪

**核心洞察：不同类型小说的"关键状态"完全不同**

| 类型 | 需要追踪什么 | 不追踪什么 |
|------|------------|-----------|
| 修仙/玄幻 | 境界、法宝、功法、灵根 | 现代社会的职业、资产 |
| 都市/商战 | 职位、资产、人际关系、秘密 | 魔法等级、战斗技能 |
| 悬疑/推理 | 线索状态、嫌疑人不在场证明 | 战斗能力、感情线 |

**Genre Template 系统**：

```python
XIANXIA_TEMPLATE = {
    "characters": {
        "fields": ["realm", "cultivation_method", "magic_treasures", 
                   "skills", "physical_state", "mental_state"],
    },
    "events": {
        "fields": ["event_type", "participants", "consequences", "location"],
    },
    "world": {
        "fields": ["location_rules", "power_structure", "hidden_forces", 
                   "time_line", "special_rules"],
    },
}
```

**自动匹配**：用户填写 genre="修仙"时，系统自动使用修仙模板；genre="都市"时使用都市模板。

### 4.3 Delta 提取与合并

**核心流程**：每章生成后，自动提取变更 → 合并到全局状态 → 记录历史

**Step 1: Delta 提取（用 LLM）**

```
输入：本章正文 + 当前 world_state + Genre Template
输出：结构化 Delta（仅包含变化的部分）

示例输出：
{
  "changed_in_chapter": 5,
  "characters": {
    "张三": {
      "changed_fields": ["realm", "magic_treasures"],
      "realm": "筑基中期",           // 从筑基初期升级
      "magic_treasures": ["玄铁剑", "聚灵丹"]  // 新增聚灵丹
    }
  },
  "events": {
    "宗门大比": {
      "changed_fields": ["status"],
      "status": "进行中"              // 从未开始变为进行中
    }
  }
}
```

**关键设计**：
- 只让 LLM 输出"变化的部分"，不输出未变化的（节省 token，减少幻觉）
- 如果本章无变化，输出 `{"no_changes": true}`
- 已死亡/离开的角色必须标记 status，后续章节的 Prompt 中会明确禁止其出场

**Step 2: 状态合并**

```python
def merge_world_state(old_state: dict, delta: dict) -> dict:
    # 深拷贝，避免副作用
    state = copy.deepcopy(old_state)
    
    # 遍历 delta 的每个变更
    for category in ["characters", "events", "world"]:
        for entity_key, fields in delta.get(category, {}).items():
            for field_name, new_value in fields.items():
                old_value = state.get(category, {}).get(entity_key, {}).get(field_name)
                
                if old_value != new_value:
                    # 记录变更历史
                    history_entry = {
                        "chapter": delta["changed_in_chapter"],
                        "category": category,
                        "key": entity_key,
                        "field": field_name,
                        "old": old_value,
                        "new": new_value,
                    }
                    state["history"].append(history_entry)
                    
                    # 更新状态
                    state[category][entity_key][field_name] = new_value
    
    return state
```

**变更历史的作用**：
- 前端可视化："张三在第 5 章从筑基初期升级到筑基中期"
- 可追溯：如果发现有矛盾，可以回溯到哪一章导致的
- 可回滚：未来支持快照恢复时，可以精确回滚到某一章的状态

### 4.4 状态摘要注入

**问题：world_state 可能很大（几十个角色 × 十几个字段），全部注入 Prompt 会超限**

**解决方案：智能筛选**

```python
async def build_state_summary(world_state, target_chapter, chapter_title, llm_config):
    # 1. 精简 world_state（减少 token）
    slim_state = {
        "characters": 取最近 3 章有变更的角色（最多 10 个）,
        "events": 取进行中且与本章相关的事件,
        "world": 取与本章地点/时间相关的设定,
        "history": 只保留最近 3 章的变更记录,
    }
    
    # 2. 让 LLM 筛选最相关的 5-10 条
    prompt = f"""
    从以下世界状态中，筛选出与第{target_chapter}章《{chapter_title}》最相关的状态信息。
    
    优先包含：
    - 本章出场角色的当前状态
    - 正在推进中且与本章相关的事件
    - 即将到期的期限/倒计时
    - 最近发生变化的状态
    
    忽略：
    - 已死亡/离开且本章不会出场的角色
    - 已完成/失败的事件
    - 与本章剧情无关的远距离角色
    """
    
    summary = await llm.generate(prompt)
    return summary  # 5-10 条简洁条目
```

**注入位置**：`next_chapter_draft_prompt` 中的 `{world_state_summary}` 占位符。

**效果**：
- 第 5 章生成时，Prompt 中包含："张三：筑基中期，持有玄铁剑（破损），与李四敌对"
- 第 20 章生成时，即使第 5 章的内容已超出 LLM 的原始上下文窗口，world_state_summary 仍确保 AI 知道张三的当前状态

---

## 5. Prompt 工程体系

### 5.1 设计原则

| 原则 | 实践 |
|------|------|
| **单一职责** | 每个 Prompt 只负责一个任务（不混合生成 + 校验） |
| **输入输出明确** | 明确标注输入占位符和输出格式要求 |
| **约束前置** | 所有"禁止"和"必须"放在 Prompt 开头 |
| **示例驱动** | 复杂格式提供示例（如角色状态文档格式） |
| **自检机制** | 关键任务后接校验 Prompt（如一致性检查） |

### 5.2 Prompt 分层架构

```
Layer 1: 系统角色定义
    "你是一位专业小说作家..."

Layer 2: 任务描述
    "请根据以下信息创作第 N 章正文..."

Layer 3: 输入数据
    "【小说设定】... 【角色状态】... 【世界状态摘要】..."

Layer 4: 约束条件
    "必须严格遵循【世界状态摘要】... 禁止出现矛盾..."

Layer 5: 输出格式
    "仅返回章节正文，不要输出标题..."
```

### 5.3 温度参数策略

| 任务类型 | temperature | 理由 |
|---------|-------------|------|
| 架构生成 | 0.3 | 需要逻辑严谨，减少随机性 |
| 章节生成 | 0.7 | 需要创意，但不过分发散 |
| 状态提取 | 0.2 | 需要精确，减少幻觉 |
| 一致性校验 | 0.2 | 需要客观判断 |

---

## 6. 数据流转全景图

### 6.1 小说创作完整流转

```
用户创建项目
    │
    ▼
[project_assets] 创建空记录
    │
    ▼
用户点击"生成架构"
    │
    ▼
[tasks] 创建 architecture 任务 (status=pending)
    │
    ▼
Celery Worker 消费任务
    │
    ▼
Step 1: Core Seed ──► Step 2: Character Dynamics
    │                       │
    ▼                       ▼
Step 3: World Building ◄──┘
    │
    ▼
Step 4: Plot Architecture
    │
    ▼
Step 5: Consistency Check
    │
    ▼
合并为 architecture_text
    │
    ▼
生成 character_state_text（基于角色动力学）
    │
    ▼
[project_assets] architecture = architecture_text
[project_assets] characters = character_state_text
[tasks] status = success, progress = 100%
    │
    ▼
用户点击"生成目录"
    │
    ▼
读取 architecture + 用户指定的 num_chapters
    │
    ▼
LLM 生成目录（含 6 维度设计）
    │
    ▼
解析为结构化数据 → 初始化 chapters 表（N 条记录，status=pending）
[project_assets] directory = 目录文本
    │
    ▼
用户点击"生成第 N 章"
    │
    ▼
读取：architecture + directory + character_state + world_state
    │
    ▼
build_state_summary() 筛选相关状态
    │
    ▼
构建 Prompt（含 5 项上下文）
    │
    ▼
LLM 生成章节正文
    │
    ▼
一致性校验（角色/情节/世界观）
    │
    ▼
[chapters] draft = 正文, status = draft_generated
    │
    ▼
更新 character_state（基于本章内容）
    │
    ▼
extract_world_state_delta() 提取变更
    │
    ▼
merge_world_state() 合并到 world_state
    │
    ▼
[project_assets] world_state = 更新后的状态
[project_assets] characters = 更新后的角色状态
```

### 6.2 短剧改编完整流转

```
用户选择项目 → 进入短剧 Tab
    │
    ▼
用户点击"生成改编计划"
    │
    ▼
读取：architecture + 所有章节正文
    │
    ▼
按每 3 章分组 → 逐组生成 episode outline
    │
    ▼
[drama_episodes] 创建记录，outline_json = 大纲
    │
    ▼
用户选择单集 → 点击"生成脚本"
    │
    ▼
读取：episode outline + 对应章节原文
    │
    ▼
查询前集脚本（如有）→ build_context_summary()
    │
    ▼
构建 Prompt（含前情提要 + 角色设定 + 大纲 + 原文）
    │
    ▼
LLM 生成分镜脚本（JSON）
    │
    ▼
_parse_llm_json() 解析并补全截断括号
    │
    ▼
[drama_episodes] script_json = 脚本
```

---

## 附录：核心算法复杂度

| 操作 | 时间复杂度 | 说明 |
|------|-----------|------|
| 架构生成（5 步） | O(5 × T_llm) | 5 次串行 LLM 调用，无法并行（每步依赖前一步） |
| 目录生成 | O(T_llm) | 1 次 LLM 调用 |
| 单章生成 | O(T_llm + T_extract + T_merge) | 生成 + 状态提取 + 合并 |
| 状态合并 | O(C + E + W) | C=角色数, E=事件数, W=世界设定数 |
| 状态摘要 | O(T_llm) | 1 次 LLM 调用 |
| 短剧计划 | O(N/3 × T_llm) | N=章节数，每 3 章生成 1 集 |
| 短剧脚本 | O(T_llm_long) | 12000 tokens，时间较长 |

---

*文档版本：v1.0*
*更新日期：2026-05-10*
