"""
导出模块
将生成的剧本导出为 Markdown 或 CSV 格式
"""

import json
import csv
from pathlib import Path
from typing import Dict


class Exporter:
    """剧本导出器"""
    
    def __init__(self, output_dir: str = "./output"):
        """
        初始化
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def export_markdown(self, script: Dict, filename: str = None) -> str:
        """
        导出为 Markdown 格式
        
        Args:
            script: 分镜头剧本字典
            filename: 文件名（不含扩展名）
        
        Returns:
            输出文件路径
        """
        if filename is None:
            episode_num = script.get("episode_num", 1)
            filename = f"episode_{episode_num:03d}"
        
        output_path = self.output_dir / f"{filename}.md"
        
        # 构建 Markdown 内容
        md_lines = []
        
        # 标题
        md_lines.append(f"# {script.get('title', '未命名剧集')}")
        md_lines.append("")
        md_lines.append(f"**集数**: 第 {script.get('episode_num', 1)} 集")
        md_lines.append(f"**总时长**: {script.get('total_duration', '未知')}")
        md_lines.append(f"**总镜头数**: {script.get('total_shots', 0)}")
        md_lines.append("")
        
        # 场景
        for scene in script.get("scenes", []):
            md_lines.append(f"## 场景 {scene['scene_num']}")
            md_lines.append("")
            md_lines.append(f"- **地点**: {scene.get('location', '未知')}")
            md_lines.append(f"- **时间**: {scene.get('time', '未知')}")
            md_lines.append(f"- **内外**: {scene.get('interior_exterior', '未知')}")
            md_lines.append(f"- **人物**: {', '.join(scene.get('characters', []))}")
            md_lines.append(f"- **氛围**: {scene.get('mood', '未知')}")
            md_lines.append("")
            
            # 镜头
            for shot in scene.get("shots", []):
                md_lines.append(f"### 镜头 {shot['shot_num']} ({shot.get('duration', '未知')})")
                md_lines.append("")
                md_lines.append(f"- **类型**: {shot.get('type', '未知')}")
                md_lines.append(f"- **画面**: {shot.get('visual', '未知')}")
                md_lines.append(f"- **动作**: {shot.get('action', '未知')}")
                md_lines.append(f"- **运镜**: {shot.get('camera_movement', '未知')}")
                md_lines.append("")
                
                # 台词
                dialogue = shot.get("dialogue")
                if dialogue:
                    md_lines.append(f"**{dialogue.get('speaker', '未知')}**:")
                    md_lines.append(f"> {dialogue.get('content', '未知')}")
                    if dialogue.get("emotion"):
                        md_lines.append(f"> *{dialogue.get('emotion')}*")
                    if dialogue.get("note"):
                        md_lines.append(f"> （{dialogue.get('note')}）")
                    md_lines.append("")
                
                # 音效
                audio = shot.get("audio", {})
                if audio:
                    md_lines.append(f"**音效**:")
                    if audio.get("bgm"):
                        md_lines.append(f"- BGM: {audio.get('bgm')}")
                    if audio.get("sfx"):
                        md_lines.append(f"- SFX: {', '.join(audio.get('sfx', []))}")
                    md_lines.append("")
            
            md_lines.append("---")
            md_lines.append("")
        
        # 改编说明
        if script.get("adaptation_notes"):
            md_lines.append("## 改编说明")
            md_lines.append("")
            md_lines.append(script["adaptation_notes"])
            md_lines.append("")
        
        # 写入文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))
        
        print(f"✅ Markdown 导出成功: {output_path}")
        return str(output_path)
    
    def export_csv(self, script: Dict, filename: str = None) -> str:
        """
        导出为 CSV 格式（便于导入剪辑软件）
        
        Args:
            script: 分镜头剧本字典
            filename: 文件名（不含扩展名）
        
        Returns:
            输出文件路径
        """
        if filename is None:
            episode_num = script.get("episode_num", 1)
            filename = f"episode_{episode_num:03d}"
        
        output_path = self.output_dir / f"{filename}.csv"
        
        # CSV 字段
        fieldnames = [
            "集数", "场景号", "镜头号", "类型", "时长",
            "地点", "时间", "内外", "人物",
            "画面", "动作", "运镜",
            "说话人", "台词", "情绪", "表演提示",
            "BGM", "音效", "氛围"
        ]
        
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for scene in script.get("scenes", []):
                for shot in scene.get("shots", []):
                    dialogue = shot.get("dialogue") or {}  # 修复：确保 dialogue 不是 None
                    audio = shot.get("audio") or {}  # 修复：确保 audio 不是 None
                    
                    row = {
                        "集数": script.get("episode_num", 1),
                        "场景号": scene.get("scene_num", ""),
                        "镜头号": shot.get("shot_num", ""),
                        "类型": shot.get("type", ""),
                        "时长": shot.get("duration", ""),
                        "地点": scene.get("location", ""),
                        "时间": scene.get("time", ""),
                        "内外": scene.get("interior_exterior", ""),
                        "人物": ", ".join(scene.get("characters", [])),
                        "画面": shot.get("visual", ""),
                        "动作": shot.get("action", ""),
                        "运镜": shot.get("camera_movement", ""),
                        "说话人": dialogue.get("speaker", ""),
                        "台词": dialogue.get("content", ""),
                        "情绪": dialogue.get("emotion", ""),
                        "表演提示": dialogue.get("note", ""),
                        "BGM": audio.get("bgm", ""),
                        "音效": ", ".join(audio.get("sfx", [])),
                        "氛围": scene.get("mood", "")
                    }
                    
                    writer.writerow(row)
        
        print(f"✅ CSV 导出成功: {output_path}")
        return str(output_path)
    
    def export_json(self, script: Dict, filename: str = None) -> str:
        """
        导出为 JSON 格式（便于程序处理）
        
        Args:
            script: 分镜头剧本字典
            filename: 文件名（不含扩展名）
        
        Returns:
            输出文件路径
        """
        if filename is None:
            episode_num = script.get("episode_num", 1)
            filename = f"episode_{episode_num:03d}"
        
        output_path = self.output_dir / f"{filename}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(script, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON 导出成功: {output_path}")
        return str(output_path)
    
    def export_all(self, script: Dict, filename: str = None, formats: list = None) -> list:
        """
        导出所有格式
        
        Args:
            script: 分镜头剧本字典
            filename: 文件名（不含扩展名）
            formats: 导出格式列表（默认全部）
        
        Returns:
            输出文件路径列表
        """
        if formats is None:
            formats = ["json", "markdown", "csv"]
        
        output_paths = []
        
        if "json" in formats:
            output_paths.append(self.export_json(script, filename))
        
        if "markdown" in formats:
            output_paths.append(self.export_markdown(script, filename))
        
        if "csv" in formats:
            output_paths.append(self.export_csv(script, filename))
        
        return output_paths


# 测试代码
if __name__ == "__main__":
    # 示例用法
    exporter = Exporter("./output")
    
    # 测试脚本
    test_script = {
        "episode_num": 1,
        "title": "测试剧集",
        "total_duration": "90 秒",
        "total_shots": 1,
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
                        "visual": "主角眼神坚定",
                        "action": "主角深吸一口气",
                        "camera_movement": "固定",
                        "dialogue": {
                            "speaker": "主角",
                            "content": "这一次，我不会再输。",
                            "emotion": "坚定"
                        },
                        "audio": {
                            "bgm": "紧张弦乐",
                            "sfx": ["心跳声"]
                        }
                    }
                ]
            }
        ]
    }
    
    # 导出所有格式
    exporter.export_all(test_script, "test_episode")
