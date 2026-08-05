# V3 P2-B 角色卡系统 + known_by 设计（V2）

- 日期：2026-08-06
- 状态：设计草案（待审）
- 目标项目：`/Users/yxx/Desktop/novel_drama_v2`

## 背景

当前 `characters` 资产是**无限增长的文本**（每章 LLM 更新后持续变大），10 章以上上下文被稀释。前沿（QMAI/AI Fiction Studio/long-novel-writer）做法是**结构化角色卡**：人设/当前状态/关系/**认知边界 known_by**，写前只加载出场角色。

## 设计

### ① 结构化角色卡（characters 资产重构）

`characters` 资产从文本 → 结构化 JSON：
```json
{
  "characters": {
    "林晚": {
      "profile": "人设：性格/背景/外貌/说话风格",
      "current_state": {"情绪": "坚毅", "目标": "追查组织", "状态": "重伤"},
      "relations": {"陈默": "搭档"},
      "known": ["知道自己的记忆被卖", "不知道幕后组织身份"],
      "last_appearance": 5,
      "trajectory": ["第1章觉醒", "第5章决定追查"]
    }
  }
}
```

### ② 更新机制（每章写后）

新 prompt `character_card_update_prompt`：输入旧角色卡 + 本章草稿 + 本章出场角色 → 更新出场角色卡（状态/关系/known 变化）+ 新增角色 + 更新 last_appearance。

新函数 `update_character_cards(db, project_id, chapter, old_state, llm_config) -> dict`：调 LLM 更新 → 存回 characters 资产。

### ③ 写前只加载出场角色卡

写前确定本章出场角色（从上一章 actual_summary_json.characters 或目录本章简介提取）→ **只注入这些角色卡**（省 token，防稀释）。

新函数 `load_active_character_cards(db, project_id, chapter, llm_config) -> str`：读 characters 资产 → 筛出出场角色卡 → 渲染成文本供 prompt 注入。

### ④ 兼容旧文本

- 读 characters 资产时：若是旧文本（非 JSON），尝试 LLM 转换一次成角色卡，或降级为"原样注入文本"（不崩溃）
- 新数据用 JSON；旧数据渐进转换

### ⑤ 管线接入

- 生成章节前：`load_active_character_cards` → 注入章节 prompt（替换现在的 character_state_text）
- 生成章节后：`update_character_cards` → 存回

## 全局约束

- 每章写后多 1 次 LLM 调用（角色卡更新），可接受
- 旧项目（characters 为文本）兼容：读旧文本降级注入，不崩溃
- 不破坏既有功能（架构生成用的 character_state 由 create_character_state 生成，P2-B 管章节链路）
- 文案不出现「小红书」；构建零错误；后端测试通过
- 更新 CHANGELOG

## 涉及文件

- `backend/app/generator/prompts.py`（character_card_update_prompt）
- `backend/app/services/generation_service.py`（update_character_cards / load_active_character_cards / _render_character_cards）
- `backend/app/services/task_service.py`（章节生成接入）
- `backend/app/tests/`（测试）
- `docs/CHANGELOG.md`

## 不在范围

- 角色卡的手动编辑 UI
- known_by 的 POV 严格防火墙（本期先存 known 字段注入，不强校验）
- 伏笔系统（P2-C）
