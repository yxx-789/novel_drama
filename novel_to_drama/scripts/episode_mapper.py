"""
短剧大纲映射模块
使用 LLM 将小说章节映射为短剧大纲
"""

import json
import os
from typing import Dict, List
from pathlib import Path
import sys

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_client import LLMClient
from json_parser import parse_llm_json


class EpisodeMapper:
    """短剧大纲映射器"""
    
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
        
        # 初始化 LLM 客户端
        if self.api_key:
            self.client = LLMClient(self.api_key, self.api_url, self.model)
        else:
            self.client = None
            print("⚠️  未配置 API Key，将使用降级模式")
    
    def map_chapters_to_episode(
        self,
        chapter_texts: List[str],
        characters: Dict,
        episode_num: int,
        chapters_range: str = "1-3"
    ) -> Dict:
        """
        将多个章节映射为单集短剧大纲
        
        Args:
            chapter_texts: 章节文本列表
            characters: 角色设定
            episode_num: 集数
            chapters_range: 章节范围（如 "1-3"）
        
        Returns:
            短剧大纲字典
        """
        # 如果没有配置 API，使用降级方案
        if not self.client:
            return self._get_fallback_outline(episode_num, chapters_range)
        
        # 构建角色摘要
        char_summary = self._build_character_summary(characters)
        
        # 合并章节文本
        combined_text = "\n\n".join(chapter_texts)
        
        # 记录原始长度
        original_length = len(combined_text)
        
        # 截断过长文本（避免超过 token 限制）
        max_chars = 15000  # 增加到 15000 字符
        if len(combined_text) > max_chars:
            combined_text = combined_text[:max_chars] + "\n... (文本已截断)"
            print(f"   ⚠️  文本过长，已截断（{original_length:,} → {max_chars:,} 字符）")
        
        # 构建 Prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            combined_text,
            char_summary,
            episode_num,
            chapters_range
        )
        
        try:
            # 调用 LLM（增加超时时间到 180 秒）
            response = self.client.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=2000,
                timeout=180  # 3 分钟超时
            )
            
            if response:
                # 使用增强的 JSON 解析器
                outline = parse_llm_json(response)
                
                if outline:
                    print("   ✅ 大纲生成完成")
                    print(f"      标题：{outline.get('title', '未知')}")
                    print(f"      时长：{outline.get('duration_estimate', '未知')}")
                    print(f"      反转：{outline.get('reversal_count', 0)} 次")
                    return outline
                else:
                    print("⚠️  LLM 响应解析失败，使用降级方案（示例数据）")
                    print("   💡 提示：降级方案不会基于你的原文生成，建议检查 API Key 或网络连接")
                    return self._get_fallback_outline(episode_num, chapters_range)
            else:
                print("⚠️  LLM 调用失败，使用降级方案（示例数据）")
                print("   💡 提示：降级方案不会基于你的原文生成，建议检查 API Key 或网络连接")
                return self._get_fallback_outline(episode_num, chapters_range)
        
        except Exception as e:
            print(f"❌ LLM 调用失败: {e}")
            return self._get_fallback_outline(episode_num, chapters_range)
    
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        
        重点：
        1. 安全性 - 避免触发 content_filter
        2. 专业性 - 符合短剧创作规律
        3. 结构化 - 强制输出 JSON
        """
        return """你是一位专业的竖屏微短剧编剧，擅长将网络小说改编为节奏紧凑、爽点密集的短剧脚本。

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
    
    def _build_user_prompt(
        self,
        chapter_text: str,
        character_summary: str,
        episode_num: int,
        chapters_range: str
    ) -> str:
        """构建用户提示词"""
        return f"""请将以下小说章节改编为第 {episode_num} 集短剧大纲。

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
    
    def _parse_json_response(self, content: str) -> Dict:
        """解析 JSON 响应"""
        # 方法1：直接解析
        try:
            result = json.loads(content)
            if isinstance(result, dict):
                return result
        except Exception as e:
            print(f"   JSON 直接解析失败: {e}")
        
        # 方法2：提取 JSON 块（```json ... ```）
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                if isinstance(result, dict):
                    print("   ✅ 从 ```json 块中提取成功")
                    return result
            except Exception as e:
                print(f"   ```json 块解析失败: {e}")
        
        # 方法3：提取花括号内容
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                result = json.loads(json_match.group())
                if isinstance(result, dict):
                    print("   ✅ 从花括号中提取成功")
                    return result
            except Exception as e:
                print(f"   花括号内容解析失败: {e}")
        
        # 方法4：尝试修复常见错误
        try:
            # 移除注释
            content_fixed = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            content_fixed = re.sub(r'/\*[\s\S]*?\*/', '', content_fixed)
            
            result = json.loads(content_fixed)
            if isinstance(result, dict):
                print("   ✅ 修复后解析成功")
                return result
        except:
            pass
        
        print("   ❌ 所有 JSON 解析方法都失败了")
        print(f"   LLM 返回内容前 200 字符: {content[:200]}")
        return None
    
    def _get_fallback_outline(self, episode_num: int, chapters_range: str) -> Dict:
        """降级方案：返回示例大纲"""
        return {
            "episode_num": episode_num,
            "title": "第 {episode_num} 集",
            "chapters_covered": f"第 {chapters_range} 章",
            "duration_estimate": "90 秒",
            "hook": {
                "first_3s": {
                    "visual": "主角特写",
                    "action": "主角抬头，眼神坚定",
                    "dialogue": "这一次，我不会再输。"
                }
            },
            "story_beats": [
                {
                    "beat_num": 1,
                    "type": "setup",
                    "description": "主角登场，展现目标",
                    "emotion": "好奇",
                    "duration": "15 秒"
                },
                {
                    "beat_num": 2,
                    "type": "conflict",
                    "description": "遭遇阻碍，陷入困境",
                    "emotion": "紧张",
                    "duration": "20 秒"
                },
                {
                    "beat_num": 3,
                    "type": "reversal",
                    "description": "出现转机，实力展现",
                    "emotion": "惊喜",
                    "duration": "25 秒"
                },
                {
                    "beat_num": 4,
                    "type": "climax",
                    "description": "高潮对决，碾压对手",
                    "emotion": "爽快",
                    "duration": "20 秒"
                }
            ],
            "cliffhanger": {
                "last_5s": {
                    "visual": "主角背影，远处出现神秘身影",
                    "action": "主角停下脚步，回头",
                    "dialogue": "你...怎么来了？",
                    "suspense_type": "人物"
                }
            },
            "key_characters": ["主角"],
            "reversal_count": 2,
            "爽点_tags": ["逆袭", "实力展现"],
            "adaptation_notes": "这是降级示例大纲，请检查 LLM 配置"
        }


# 测试代码
if __name__ == "__main__":
    # 示例用法
    mapper = EpisodeMapper()
    
    # 测试降级方案
    outline = mapper._get_fallback_outline(1, "1-3")
    print("📝 降级大纲:")
    print(json.dumps(outline, ensure_ascii=False, indent=2))
