"""
短剧脚本导出服务
复用 novel_to_drama/scripts/exporter.py 核心格式化逻辑，改造为纯内存操作（无文件 IO）
"""

import csv
import io
import json
from typing import Dict, Tuple


class Exporter:
    """剧本导出器 — 纯内存版本，返回字符串供 API 直接响应"""

    @staticmethod
    def export_json(script: Dict, filename: str = None) -> Tuple[str, str, str]:
        """
        导出为 JSON 格式
        返回: (content, media_type, download_filename)
        """
        content = json.dumps(script, ensure_ascii=False, indent=2)
        episode_num = script.get("episode_num", 1)
        fname = filename or f"episode_{episode_num:03d}"
        return content, "application/json", f"{fname}.json"

    @staticmethod
    def export_markdown(script: Dict, filename: str = None) -> Tuple[str, str, str]:
        """
        导出为 Markdown 格式
        返回: (content, media_type, download_filename)
        """
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
                    md_lines.append("**音效**:")
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

        content = "\n".join(md_lines)
        episode_num = script.get("episode_num", 1)
        fname = filename or f"episode_{episode_num:03d}"
        return content, "text/markdown; charset=utf-8", f"{fname}.md"

    @staticmethod
    def export_csv(script: Dict, filename: str = None) -> Tuple[str, str, str]:
        """
        导出为 CSV 格式（便于导入剪辑软件）
        返回: (content, media_type, download_filename)
        """
        fieldnames = [
            "集数", "场景号", "镜头号", "类型", "时长",
            "地点", "时间", "内外", "人物",
            "画面", "动作", "运镜",
            "说话人", "台词", "情绪", "表演提示",
            "BGM", "音效", "氛围"
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for scene in script.get("scenes", []):
            for shot in scene.get("shots", []):
                dialogue = shot.get("dialogue") or {}
                audio = shot.get("audio") or {}

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

        content = output.getvalue()
        episode_num = script.get("episode_num", 1)
        fname = filename or f"episode_{episode_num:03d}"
        return content, "text/csv; charset=utf-8-sig", f"{fname}.csv"


def export_script(script: Dict, format: str, filename: str = None) -> Tuple[str, str, str]:
    """
    统一导出入口

    Args:
        script: 分镜头剧本字典（DramaEpisode.script_json）
        format: json | md | csv
        filename: 文件名前缀（不含扩展名）

    Returns:
        (content, media_type, download_filename)
    """
    if format == "json":
        return Exporter.export_json(script, filename)
    elif format in ("md", "markdown"):
        return Exporter.export_markdown(script, filename)
    elif format == "csv":
        return Exporter.export_csv(script, filename)
    else:
        raise ValueError(f"Unsupported export format: {format}. Use json, md, or csv.")
