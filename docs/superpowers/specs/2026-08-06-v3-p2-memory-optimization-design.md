# V3 P2 记忆优化（全对齐前沿）设计（V2）

- 日期：2026-08-06
- 状态：设计草案（待审）
- 目标项目：`/Users/yxx/Desktop/novel_drama_v2`

## 背景

当前章节记忆 3 缺陷：前章"概要"用计划 outline 非实际内容、前章窗口固定 1500 字、角色状态无限增长。对照前沿（QMAI/AI Fiction Studio/Alex/long-novel-writer），方案全对齐：**结构化章节记忆 + 角色卡 known_by + 上下文优先级装配 + 伏笔追踪 + 动态前章窗口**。

## 设计

### ① 结构化章节记忆（每章写后自动提取）

`Chapter` 加 `actual_summary_json`（JSONB）：
```json
{
  "summary": "精炼摘要（150-300字，供 prompt 注入）",
  "hook": "结尾钩子（留给下章的悬念）",
  "characters": ["林晚", "陈默"],
  "relations_changed": {"林晚-陈默": "从对立到结盟"},
  "foreshadowing_added": [{"name": "神秘组织", "note": "第3章埋下"}],
  "connects_to": "下章方向（留给下一章的续接点）"
}
```

新 prompt `chapter_memory_extract_prompt`：输入章节草稿 → 输出上述结构化 JSON。

### ② 角色卡系统（结构化 + known_by 认知边界）

`characters` 资产重构为结构化角色卡 JSON：
```json
{
  "characters": {
    "林晚": {
      "profile": "人设：性格/背景/外貌/说话风格",
      "current_state": {"情绪": "坚毅", "目标": "追查组织", "状态": "重伤"},
      "relations": {"陈默": "搭档"},
      "known": ["知道自己记忆被卖", "不知道幕后组织身份"],
      "last_appearance": 5,
      "trajectory": ["第1章觉醒", "第5章决定追查"]
    }
  }
}
```

- 新 prompt `character_card_update_prompt`：输入旧角色卡 + 本章草稿 → 更新出场角色卡（状态/关系/known 变化）+ 新增角色
- 写前**只加载本章出场角色卡**（从 chapter 目录/上一章摘要取出场角色，或全量但裁剪）
- **known_by 认知边界**：known 字段注入章节 prompt，防角色用未获得的信息

### ③ 伏笔追踪（pending_hooks）

新资产 `pending_hooks`（JSONB）：
```json
[{"name": "神秘组织", "status": "planted", "planted_chapter": 3, "note": "黑衣人"},
 {"name": "玉佩", "status": "advancing", "planted_chapter": 2, "last_chapter": 5}]
```

- 新 prompt `hook_update_prompt`：输入旧伏笔 + 本章草稿 → 更新伏笔（新增 planted / 推进 advancing / 回收 resolved）
- 章节 prompt 注入【伏笔状态】：未回收伏笔清单（写前提醒回收，防伏笔烂尾）

### ④ 上下文优先级装配器

新函数 `assemble_chapter_context(...)`：写前按优先级装配上下文包：
```
① 创作意图 > ② 当前细纲 > ③ 前章结尾（动态窗口）> ④ 世界观 Canon > ⑤ 出场角色卡 > ⑥ 伏笔状态 > ⑦ 最近章节摘要 > ⑧ 内部风味
```
带 token 预算控制（超限裁剪低优先级项）。

### ⑤ 动态前章窗口

`_chapter_excerpt(draft)`：取结尾 20%（下限 800、上限 2000），替换固定 `[-1500:]`。

## 全局约束

- 每章写后多 2 次 LLM 调用（摘要提取 + 角色卡/伏笔更新），可接受
- 旧项目（无 actual_summary_json/结构化角色卡）→ 回退旧路径（outline + 文本角色状态），行为兼容
- `characters` 资产从文本 → JSON 是**数据格式变更**，需兼容旧文本（读旧文本时先用 LLM 或跳过结构化，仅新数据用结构化）——**迁移策略**：生成时若 characters 是文本，先用 prompt 转成角色卡；后续持续用 JSON
- 不破坏既有功能（生成/短剧/导出）；文案不出现「小红书」；构建零错误；后端测试通过
- 更新 CHANGELOG

## 涉及文件

- `backend/app/models/project.py`（Chapter.actual_summary_json）+ Alembic 迁移
- `backend/app/generator/prompts.py`（chapter_memory_extract_prompt / character_card_update_prompt / hook_update_prompt）
- `backend/app/services/generation_service.py`（_chapter_excerpt / assemble_chapter_context / 提取/更新函数）
- `backend/app/services/task_service.py`（章节生成接入：装配上下文 → 生成 → 提取摘要 → 更新角色卡/伏笔）
- `backend/app/tests/`（测试）
- `docs/CHANGELOG.md`

## 实施阶段（建议）

| 阶段 | 内容 | 依赖 |
|---|---|---|
| **P2-A** | 数据模型 + 动态窗口 + 结构化摘要提取 | 无 |
| **P2-B** | 角色卡系统 + known_by | A |
| **P2-C** | 伏笔追踪 + 上下文装配器 + 管线接入 | A,B |
| 验证 | 端到端（长篇小说生成看衔接质量） | 全 |

## 不在范围

- 分层分卷摘要（L2-L5，后置）
- RAG 向量检索
- 前情/角色卡的手动编辑 UI
