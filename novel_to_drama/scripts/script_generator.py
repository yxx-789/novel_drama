"""
剧本生成模块
根据短剧大纲生成标准的分镜头脚本
"""

import json
import os
from typing import Dict, List
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import LLMClient
from json_parser import parse_llm_json


class ScriptGenerator:
    """分镜头剧本生成器"""
    
    def __init__(self, api_key: str = None, api_url: str = None, model: str = "glm-5.1"):
        """
        初始化
        
        Args:
            api_key: API 密钥
            api_url: API URL
            model: 模型名称
        """
        self.api_key = api_key or os.getenv("QIANFAN_API_KEY")
        self.api_url = api_url or "https://qianfan.baidubce.com/v2/chat/completions"
        self.model = model
        
        if self.api_key:
            self.client = LLMClient(self.api_key, self.api_url, self.model)
        else:
            self.client = None
            print("⚠️  未配置 API Key，将使用降级模式")
    
    def generate_script(
        self,
        outline: Dict,
        chapter_text: str,
        characters: Dict
    ) -> Dict:
        """
        根据大纲生成分镜头剧本
        
        Args:
            outline: 短剧大纲
            chapter_text: 原始小说文本
            characters: 角色设定
        
        Returns:
            分镜头剧本字典
        """
        if not self.client:
            return self._get_fallback_script(outline)
        
        # 构建角色摘要
        char_summary = self._build_character_summary(characters)
        
        # 构建 Prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(outline, chapter_text, char_summary)
        
        try:
            # 调用 LLM（增加超时时间到 300 秒）
            response = self.client.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=4000,
                timeout=300  # 5 分钟超时（生成剧本需要更长时间）
            )
            
            if response:
                # 使用增强的 JSON 解析器
                script = parse_llm_json(response)
                
                if script:
                    print("   ✅ 剧本生成完成")
                    print(f"      场景数：{len(script.get('scenes', []))}")
                    print(f"      总镜头：{script.get('total_shots', 0)}")
                    return script
                else:
                    print("⚠️  LLM 响应解析失败，使用降级方案（示例数据）")
                    print("   💡 提示：降级方案不会基于你的原文生成，建议检查 API Key 或网络连接")
                    return self._get_fallback_script(outline)
            else:
                print("⚠️  LLM 调用失败，使用降级方案（示例数据）")
                print("   💡 提示：降级方案不会基于你的原文生成，建议检查 API Key 或网络连接")
                return self._get_fallback_script(outline)
        
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return self._get_fallback_script(outline)
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        
        重点：
        1. 格式规范 - 严格的分镜头格式
        2. 转换规则 - 心理描写转为视觉/台词
        3. 人设贴合 - 台词符合角色性格
        """
        return """你是一位专业的竖屏微短剧编剧，擅长将大纲转化为具体的分镜头脚本。

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

### 2. 分镜头格式

每个场景必须包含以下字段：

```json
{
  "scene_num": 1,
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

**台词冲突感示例**：

| 无冲突 | 有冲突 |
|--------|--------|
| 我知道了 | 你以为我会信？ |
| 我会努力的 | 这次，我一定赢 |
| 她为什么不理我 | 她凭什么这么对我？ |
| 我不想去 | 去不去，由不得你 |

### 4. 节奏控制

- **建立镜头**：4-6 秒，交代环境
- **对话镜头**：2-3 秒，快速切换
- **动作镜头**：1-2 秒，强调冲击
- **反应镜头**：1-1.5 秒，突出情绪

### 5. 镜头运动

- **推镜头**：强调情绪、制造压迫感
- **拉镜头**：展现全貌、制造距离感
- **摇镜头**：跟随动作、展现环境
- **固定镜头**：突出表情、强调对话

### 6. 音效设计

- **BGM**：烘托氛围（紧张/温馨/激烈）
- **SFX**：增强真实感（脚步声/门声/风声）
- **情绪音效**：强调心理（心跳声/耳鸣声）

### 7. 竖屏适配

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
  
  "adaptation_notes": "改编说明"
}
```

记住：每一帧画面都要服务于"让观众停不下来"。台词要短、画面要美、节奏要快。"""
    
    def _build_user_prompt(
        self,
        outline: Dict,
        chapter_text: str,
        char_summary: str
    ) -> str:
        """构建用户提示词"""
        outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
        
        # 截断小说文本
        max_chars = 6000
        if len(chapter_text) > max_chars:
            chapter_text = chapter_text[:max_chars] + "\n... (文本已截断)"
        
        return f"""请根据以下短剧大纲生成分镜头剧本。

## ⚠️ 重要提示

**不要跳过大纲中的任何 story_beats！** 每个 beat 都要有对应的场景和镜头。
**不要忽略大纲中的 key_items！** 关键道具/信息必须在剧本中体现。

## 角色设定

{char_summary}

## 短剧大纲

{outline_json}

## 原始小说片段

{chapter_text}

## 任务要求

### 必须做到：
1. **严格按照大纲的 story_beats 生成**：每个 beat 都要有对应的场景和镜头
2. **保留大纲中的 key_items**：关键道具/信息必须在剧本中体现
3. **保留逻辑链条**：前因后果必须清晰，不能跳跃导致观众看不懂
4. 所有心理描写必须转为视觉动作或台词
5. 台词要短、狠、符合人设
6. 每个镜头时长控制在 1-6 秒
7. 设计合适的镜头运动和音效
8. 预留字幕空间（竖屏适配）

### 检查清单：
- ✅ 是否覆盖了大纲中的所有 story_beats？
- ✅ 是否体现了大纲中的 key_items？
- ✅ 逻辑是否连贯？观众能看懂吗？
- ✅ 场景数是否足够（建议 5-10 个场景）？
- ✅ 镜头数是否足够（建议 20-40 个镜头）？

请直接输出 JSON 格式的分镜头剧本，不要添加任何额外说明。"""
    
    def _build_character_summary(self, characters: Dict) -> str:
        """构建角色设定摘要"""
        if not characters:
            return "（未提供角色设定）"
        
        lines = []
        for name, info in characters.items():
            lines.append(f"**{name}**")
            if isinstance(info, dict):
                for key, value in info.items():
                    lines.append(f"  - {key}: {value}")
            else:
                lines.append(f"  - {info}")
        
        return "\n".join(lines)
    
    def _get_fallback_script(self, outline: Dict) -> Dict:
        """降级方案：返回示例剧本"""
        episode_num = outline.get("episode_num", 1)
        
        return {
            "episode_num": episode_num,
            "title": outline.get("title", f"第 {episode_num} 集"),
            "total_duration": "90 秒",
            "total_shots": 12,
            
            "scenes": [
                {
                    "scene_num": 1,
                    "location": "会议室",
                    "time": "日",
                    "interior_exterior": "内",
                    "characters": ["主角"],
                    "mood": "紧张",
                    "shots": [
                        {
                            "shot_num": 1,
                            "type": "特写",
                            "duration": "2 秒",
                            "visual": "主角眼神坚定，嘴角紧抿",
                            "action": "主角深吸一口气",
                            "dialogue": {
                                "speaker": "主角",
                                "content": "这一次，我不会再输。",
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
            
            "adaptation_notes": "这是降级示例剧本，请检查 LLM 配置"
        }


# 测试代码
if __name__ == "__main__":
    generator = ScriptGenerator()
    
    # 测试降级方案
    outline = {"episode_num": 1, "title": "测试"}
    script = generator._get_fallback_script(outline)
    print("🎬 降级剧本:")
    print(json.dumps(script, ensure_ascii=False, indent=2))
