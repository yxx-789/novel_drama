# drama_service.py
# -*- coding: utf-8 -*-
"""
短剧改编服务：复用 novel_to_drama 核心 prompt 逻辑，改造为异步 + 数据库驱动
"""

import json
import logging
import re

from app.core.config import settings
from app.generator.llm_adapter import create_llm_adapter

logger = logging.getLogger(__name__)


# =============== Episode Outline Prompts ===================

_EPISODE_OUTLINE_SYSTEM_PROMPT = """你是一位专业的竖屏微短剧编剧，擅长将网络小说改编为节奏紧凑、爽点密集的短剧脚本。

## 核心原则

### 1. 关键信息保留（最重要！）
- **必须保留原文中的关键情节转折**：不要为了压缩而删除重要的剧情转折点
- **必须保留关键道具/信息**：如果原文提到重要道具、信息、线索，必须在剧本中体现
- **必须保留逻辑链条**：前因后果必须清晰，不能跳跃导致观众看不懂
- **必须保留角色动机**：角色为什么这么做？动机必须清楚

### 2. 压缩与扩展的平衡
- **打斗场景**：可以压缩，但必须保留关键动作和结果
- **对话场景**：保留关键信息，删除无意义的寒暄
- **情绪场景**：扩展到 150%，用视觉画面和动作展现
- **关键转折**：不能压缩！必须清晰展现

### 3. 节奏控制
- **开局 3 秒钩子**：必须立即抓住观众
  - 视觉冲击：动作、表情、道具
  - 信息冲击：悬念、矛盾、反转
  - 情感冲击：愤怒、委屈、惊喜

- **结尾 5 秒悬念**：必须让观众想看下一集
  - 人物悬念：主角突然出现/消失
  - 情节悬念：关键道具出现/消失
  - 关系悬念：身份曝光/误解产生

- **每集至少 3-5 次反转**：
  - 预期反转：以为 A，其实是 B
  - 立场反转：敌人变盟友/盟友变敌人
  - 信息反转：以为知道真相，其实被骗了

### 4. 爽点设计
- **打脸爽**：反派嘲讽 → 主角实力碾压
- **逆袭爽**：困境 → 突破 → 翻盘
- **身份爽**：隐藏身份曝光 → 众人震惊
- **情感爽**：误解消除 → 感情升温

### 5. 台词原则
- **短**：单句不超过 15 字
- **狠**：有冲突感、对立感
- **人设化**：符合角色性格
- **留白**：让观众自己脑补

### 6. 禁止事项
- ❌ 心理描写（"他感到愤怒" → "他攥紧拳头"）
- ❌ 长篇独白（拆分为对话 + 动作）
- ❌ 无意义的过场戏
- ❌ 平铺直叙的剧情
- ❌ **删除关键情节转折**（这是最严重的错误！）
- ❌ **跳过重要道具/信息**（会导致逻辑不连贯！）

## 输出格式

你必须严格按照以下 JSON 格式输出，不要添加任何额外文字：

```json
{
  "episode_num": 1,
  "title": "本集标题（10 字以内，吸引眼球）",
  "chapters_covered": "第 1-3 章",
  "duration_estimate": "120 秒",
  "hook": {
    "first_3s": {
      "visual": "开局画面描述（必须有视觉冲击）",
      "action": "人物动作",
      "dialogue": "第一句台词（必须有钩子）"
    }
  },
  "story_beats": [
    {
      "beat_num": 1,
      "type": "setup/conflict/reversal/climax",
      "description": "情节要点（必须包含关键信息和转折，80 字以内）",
      "key_info": "本节拍的关键信息/道具/转折",
      "emotion": "情绪走向（好奇 → 愤怒 → 期待）",
      "duration": "15 秒"
    }
  ],
  "cliffhanger": {
    "last_5s": {
      "visual": "结尾画面（必须有悬念）",
      "action": "人物动作",
      "dialogue": "最后一句台词（必须留扣子）",
      "suspense_type": "人物/情节/关系"
    }
  },
  "key_characters": ["出场角色列表"],
  "reversal_count": 3,
  "爽点_tags": ["打脸", "逆袭", "身份曝光"],
  "key_items": ["本集出现的关键道具/信息"],
  "adaptation_notes": "改编说明：保留了 XX 关键情节，压缩了 XX 场景，扩展了 XX 情绪"
}
```

记住：你是专业的短剧编剧。**节奏要快，但逻辑必须清晰**。**可以压缩细节，但不能丢失关键信息**。"""

_EPISODE_OUTLINE_USER_PROMPT = """请将以下小说章节改编为第 {episode_num} 集短剧大纲。

## ⚠️ 重要提示

**不要过度压缩！** 必须保留原文中的所有关键情节转折、重要道具、关键信息。

## 角色设定

{character_summary}

## 小说正文（第 {chapters_range} 章）

{chapter_text}

## 任务要求

### 必须做到：
1. **保留所有关键情节转折**：不要为了压缩而删除重要的剧情转折点
2. **保留关键道具/信息**：如果原文提到重要道具、信息、线索，必须在剧本中体现
3. **保留逻辑链条**：前因后果必须清晰，不能跳跃导致观众看不懂
4. **保留角色动机**：角色为什么这么做？动机必须清楚
5. 设计开局 3 秒钩子（必须有视觉或信息冲击）
6. 设计至少 3-5 次反转
7. 设计结尾 5 秒悬念（必须让观众想看下一集）
8. 台词要短、狠、有人设

### 可以压缩：
- 无意义的寒暄对话
- 重复的描写
- 不影响剧情的过场戏

### 不能压缩：
- 关键情节转折
- 重要道具/信息
- 角色动机和逻辑

请直接输出 JSON 格式的大纲，不要添加任何额外说明。"""


# =============== Script Prompts ===================

_SCRIPT_SYSTEM_PROMPT = """你是一位专业的竖屏微短剧编剧，擅长将大纲转化为具体的分镜头脚本。

## 核心原则

### 1. 绝对禁止心理描写

所有心理活动必须转为**视觉动作**或**台词**：

| 原文（禁止） | 转换后（正确） |
|------------|--------------|
| 他感到愤怒 | 他攥紧拳头，青筋暴起 |
| 她心里很委屈 | 她眼眶泛红，强忍眼泪 |
| 他暗自得意 | 他嘴角上扬，眼神玩味 |
| 她心慌意乱 | 她眼神躲闪，手微微颤抖 |
| 他下定决心 | 他深吸一口气，眼神坚定 |

### 2. 续集一致性（如果是多集剧本中的后续集数，必须遵守！）

- **角色人设必须统一**：同一角色在前集中的性格、口头禅、行为习惯必须保持一致，不能前后矛盾。
- **关键道具和信息必须延续**：前集中出现的关键道具、线索、秘密在本集中必须有交代或影响，不能凭空消失。
- **情节必须承接**：本集开头必须自然承接前集结尾的悬念或状态，不能跳跃。
- **角色关系必须一致**：前集中已确立的盟友/敌人/暧昧关系不能无故改变。
- **已揭露的信息不能再当悬念**：如果前集已经曝光了某个身份/秘密，本集不能再把它当作未知悬念使用。

### 3. 分镜头格式

每个场景必须包含以下字段：

```json
{
  "scene_num": 1,
  "source_chapter_range": "第 1 章",
  "mapped_beat_num": 1,
  "location": "场景地点",
  "time": "时间（日/夜/黄昏）",
  "interior_exterior": "内/外",
  "characters": ["出场角色"],
  "mood": "场景氛围",
  "shots": [
    {
      "shot_num": 1,
      "type": "特写/中景/远景",
      "duration": "3 秒",
      "visual": "画面描述（纯视觉，无心理）",
      "action": "人物动作",
      "dialogue": {
        "speaker": "说话人",
        "content": "台词内容",
        "emotion": "情绪提示",
        "note": "表演提示（可选）"
      },
      "camera_movement": "镜头运动（推/拉/摇/移/固定）",
      "audio": {
        "bgm": "背景音乐",
        "sfx": ["音效列表"]
      }
    }
  ]
}
```

### 3. 台词原则

- **短**：单句不超过 15 字（竖屏不适合长台词）
- **狠**：有冲突感、对立感
- **人设化**：符合角色性格（参考角色设定）
- **口语化**：避免书面语、长句

### 4. 节奏控制

- **建立镜头**：4-6 秒，交代环境
- **对话镜头**：2-3 秒，快速切换
- **动作镜头**：1-2 秒，强调冲击
- **反应镜头**：1-1.5 秒，突出情绪

### 5. 竖屏适配

- **构图**：纵向构图，突出人物上半身
- **字幕**：预留字幕空间（底部 1/3）
- **景别**：多用中景、特写，少用远景

## 输出格式

你必须严格按照以下 JSON 格式输出：

```json
{
  "episode_num": 1,
  "title": "本集标题",
  "total_duration": "90 秒",
  "total_shots": 15,
  "scenes": [
    {
      "scene_num": 1,
      "source_chapter_range": "第 1 章",
      "mapped_beat_num": 1,
      "location": "办公室",
      "time": "日",
      "interior_exterior": "内",
      "characters": ["主角", "配角A"],
      "mood": "紧张",
      "shots": [
        {
          "shot_num": 1,
          "type": "特写",
          "duration": "2 秒",
          "visual": "主角眼神锐利，嘴角紧抿",
          "action": "主角攥紧拳头",
          "dialogue": {
            "speaker": "主角",
            "content": "这次，我不会输。",
            "emotion": "坚定"
          },
          "camera_movement": "固定",
          "audio": {
            "bgm": "紧张弦乐",
            "sfx": ["心跳声"]
          }
        }
      ]
    }
  ],
  "adaptation_notes": "改编说明。末尾必须附加场景-原文映射表，格式：场景1 → 第X章（大纲beat Y）；场景2 → 第X章（大纲beat Z）..."
}
```

记住：每一帧画面都要服务于"让观众停不下来"。台词要短、画面要美、节奏要快。"""

_SCRIPT_USER_PROMPT = """请根据以下短剧大纲生成分镜头剧本。

## ⚠️ 重要提示

**不要跳过大纲中的任何 story_beats！** 每个 beat 都要有对应的场景和镜头。
**不要忽略大纲中的 key_items！** 关键道具/信息必须在剧本中体现。
**注意输出长度控制**：请将总场景数控制在 6-8 个，每个场景 2-5 个镜头，总镜头数不超过 28 个。adaptation_notes 控制在 300 字以内，确保 JSON 能完整输出不被截断。

## 前情提要（如有前集剧本，必须承接）

{context_summary}

## 角色设定

{character_summary}

## 短剧大纲

{outline_json}

## 原始小说片段

{chapter_text}

## 任务要求

### 必须做到：
1. **严格按照大纲的 story_beats 生成**：每个 beat 都要有对应的场景和镜头
2. **保留大纲中的 key_items**：关键道具/信息必须在剧本中体现
3. **保留逻辑链条**：前因后果必须清晰，不能跳跃导致观众看不懂
4. **每个场景必须标注 source_chapter_range**：填写该场景改编自原文第几章（如"第 1 章"、"第 2-3 章"）
5. **每个场景必须标注 mapped_beat_num**：填写对应大纲中的 beat_num（如 1、2、3）
6. 所有心理描写必须转为视觉动作或台词
7. 台词要短、狠、符合人设
8. 每个镜头时长控制在 1-6 秒
9. 设计合适的镜头运动和音效
10. 预留字幕空间（竖屏适配）
11. **adaptation_notes 末尾必须附加"场景-原文映射表"**，格式：场景1 → 第X章（大纲beat Y）；场景2 → 第X章（大纲beat Z）...

### 检查清单：
- ✅ 是否覆盖了大纲中的所有 story_beats？
- ✅ 是否体现了大纲中的 key_items？
- ✅ 每个 scene 是否都有 source_chapter_range 和 mapped_beat_num？
- ✅ 逻辑是否连贯？观众能看懂吗？
- ✅ 场景数是否足够（建议 5-10 个场景）？
- ✅ 镜头数是否足够（建议 20-40 个镜头）？

请直接输出 JSON 格式的分镜头剧本，不要添加任何额外说明。"""


def _parse_llm_json(content: str) -> dict | None:
    """解析 LLM 返回的 JSON，多层容错 + 截断修复"""
    if not content or not isinstance(content, str):
        return None

    # 预处理：去掉开头的 "json" 或 "JSON" 字样
    cleaned = content.strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    candidates = [cleaned]

    # 方法2：提取 JSON 块（```json ... ```）
    m = re.search(r'```json\s*([\s\S]*?)\s*```', content)
    if m:
        candidates.append(m.group(1).strip())

    # 方法3：提取花括号内容（贪婪匹配到最后一个 }）
    m = re.search(r'\{[\s\S]*\}', cleaned)
    if m:
        candidates.append(m.group().strip())

    for candidate in candidates:
        # 尝试直接解析
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except Exception:
            pass

        # 尝试修复截断：补全缺失的 } 和 ]
        fixed = candidate
        open_braces = fixed.count("{") - fixed.count("}")
        open_brackets = fixed.count("[") - fixed.count("]")
        if open_braces > 0:
            fixed += "\n" + "}" * open_braces
        if open_brackets > 0:
            fixed += "\n" + "]" * open_brackets

        try:
            result = json.loads(fixed)
            if isinstance(result, dict):
                logger.info("JSON parsed successfully after fixing truncation")
                return result
        except Exception:
            pass

    logger.warning(f"JSON parse failed, content preview: {content[:200]}")
    return None


async def _invoke_llm(prompt: str, max_retries: int = 3, max_tokens: int | None = None) -> str:
    """调用 LLM，带重试，支持自定义 max_tokens"""
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM API key not configured")

    adapter = create_llm_adapter(
        interface_format=settings.LLM_INTERFACE_FORMAT,
        base_url=settings.LLM_BASE_URL,
        model_name=settings.LLM_MODEL,
        api_key=settings.LLM_API_KEY,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
        timeout=settings.LLM_TIMEOUT,
    )

    for attempt in range(max_retries):
        try:
            result = await adapter.invoke(prompt)
            cleaned = result.replace("```", "").strip()
            if cleaned:
                return cleaned
            logger.warning(f"Empty LLM response on attempt {attempt + 1}")
        except Exception as e:
            logger.warning(f"LLM invoke failed on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise
    return ""


async def generate_drama_outline(
    chapter_texts: str,
    characters_text: str,
    episode_num: int = 1,
    chapters_range: str = "",
) -> dict:
    """
    将小说章节文本改编为单集短剧大纲（JSON）。
    复用 novel_to_drama EpisodeMapper 核心 prompt 逻辑。
    """
    # 截断小说文本防止超限
    max_chars = 8000
    if len(chapter_texts) > max_chars:
        chapter_texts = chapter_texts[:max_chars] + "\n... (文本已截断)"

    user_prompt = _EPISODE_OUTLINE_USER_PROMPT.format(
        episode_num=episode_num,
        chapters_range=chapters_range,
        chapter_text=chapter_texts,
        character_summary=characters_text or "（未提供角色设定）",
    )

    full_prompt = f"{_EPISODE_OUTLINE_SYSTEM_PROMPT}\n\n{user_prompt}"
    logger.info(f"Generating drama outline for episode {episode_num} ...")
    raw = await _invoke_llm(full_prompt)

    outline = _parse_llm_json(raw)
    if not outline:
        raise RuntimeError(f"Failed to parse drama outline JSON for episode {episode_num}")

    # 补充缺失字段
    outline.setdefault("episode_num", episode_num)
    outline.setdefault("title", f"第 {episode_num} 集")
    outline.setdefault("chapters_covered", chapters_range)
    return outline


def _build_context_summary(context_scripts: list[dict]) -> str:
    """从前几集脚本中提取关键信息，生成前情提要文本"""
    if not context_scripts:
        return "（无前集信息，这是第一集）"
    lines = []
    for cs in context_scripts[-3:]:  # 只取最近 3 集
        ep_num = cs.get("episode_num", "?")
        title = cs.get("title", "未命名")
        key_items = cs.get("key_items", [])
        cliffhanger = ""
        scenes = cs.get("scenes", [])
        if scenes:
            last_scene = scenes[-1]
            shots = last_scene.get("shots", [])
            if shots:
                last_shot = shots[-1]
                dialogue = last_shot.get("dialogue", {})
                if dialogue:
                    cliffhanger = f"最后台词：{dialogue.get('speaker', '?')}「{dialogue.get('content', '')}」"
        lines.append(f"第{ep_num}集《{title}》：关键道具/信息 {key_items}；{cliffhanger}")
    return "\n".join(lines)


async def generate_drama_script(
    outline: dict,
    chapter_texts: str,
    characters_text: str,
    context_scripts: list[dict] | None = None,
) -> dict:
    """
    根据短剧大纲和原始小说片段生成分镜头剧本（JSON）。
    复用 novel_to_drama ScriptGenerator 核心 prompt 逻辑。
    支持传入前集剧本作为上下文，保持续集一致性。
    """
    # 去掉缩进减少 token 消耗
    outline_json = json.dumps(outline, ensure_ascii=False, separators=(",", ":"))

    # 截断小说文本（大纲已包含全部 beats，原文仅作参考，不需要太长）
    max_chars = 3000
    if len(chapter_texts) > max_chars:
        chapter_texts = chapter_texts[:max_chars] + "\n... (文本已截断)"

    context_summary = _build_context_summary(context_scripts or [])

    user_prompt = _SCRIPT_USER_PROMPT.format(
        outline_json=outline_json,
        chapter_text=chapter_texts,
        character_summary=characters_text or "（未提供角色设定）",
        context_summary=context_summary,
    )

    full_prompt = f"{_SCRIPT_SYSTEM_PROMPT}\n\n{user_prompt}"
    logger.info(f"Generating drama script for episode {outline.get('episode_num', 1)} ...")
    # Script JSON 通常很长，需要更大的 token 上限
    raw = await _invoke_llm(full_prompt, max_tokens=12000)

    script = _parse_llm_json(raw)
    if not script:
        raise RuntimeError("Failed to parse drama script JSON")

    script.setdefault("episode_num", outline.get("episode_num", 1))
    script.setdefault("title", outline.get("title", "未命名"))
    return script
