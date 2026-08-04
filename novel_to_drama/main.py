#!/usr/bin/env python3
"""
Novel to Drama - 主入口
网文小说转竖屏微短剧脚本生成器
"""

import sys
import argparse
from pathlib import Path
import os

# 添加 scripts 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from data_loader import DataLoader
from episode_mapper import EpisodeMapper
from script_generator import ScriptGenerator
from exporter import Exporter
from config_manager import config


def group_by_chapter_count(loader: DataLoader, chapters_per_episode: int):
    """
    按章节数分组
    
    Args:
        loader: 数据加载器
        chapters_per_episode: 每集章节数
    
    Returns:
        分组列表 [{'start': 1, 'end': 3}, ...]
    """
    total_chapters = loader.get_chapter_count()
    groups = []
    
    for start in range(1, total_chapters + 1, chapters_per_episode):
        end = min(start + chapters_per_episode - 1, total_chapters)
        groups.append({
            'start': start,
            'end': end,
            'word_count': 0  # 按章节数分组时不计算字数
        })
    
    return groups


def group_by_word_count(loader: DataLoader, words_per_episode: int, preserve_paragraphs: bool = True):
    """
    按字数分组，保持段落完整性
    
    Args:
        loader: 数据加载器
        words_per_episode: 每集目标字符数
        preserve_paragraphs: 是否保持段落完整性
    
    Returns:
        分组列表 [{'start': 1, 'end': 2, 'word_count': 2850}, ...]
    """
    total_chapters = loader.get_chapter_count()
    groups = []
    
    current_start = 1
    current_word_count = 0
    current_chapters = []
    
    for chapter_num in range(1, total_chapters + 1):
        chapter_text = loader.get_chapter(chapter_num)
        if not chapter_text:
            continue
        
        chapter_word_count = len(chapter_text)
        
        # 如果当前章节字符数已经超过目标，且当前组为空，则单独成集
        if chapter_word_count >= words_per_episode and not current_chapters:
            groups.append({
                'start': chapter_num,
                'end': chapter_num,
                'word_count': chapter_word_count
            })
            current_start = chapter_num + 1
            current_word_count = 0
            current_chapters = []
            continue
        
        # 如果加上当前章节会超过目标
        if current_word_count + chapter_word_count > words_per_episode and current_chapters:
            # 保存当前组
            groups.append({
                'start': current_start,
                'end': chapter_num - 1,
                'word_count': current_word_count
            })
            
            # 开始新的一组
            current_start = chapter_num
            current_word_count = chapter_word_count
            current_chapters = [chapter_num]
        else:
            # 继续累加
            current_word_count += chapter_word_count
            current_chapters.append(chapter_num)
    
    # 处理最后一组
    if current_chapters:
        groups.append({
            'start': current_start,
            'end': current_chapters[-1],
            'word_count': current_word_count
        })
    
    return groups


def main():
    parser = argparse.ArgumentParser(
        description="🎬 Novel to Drama - 网文转短剧脚本生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 处理单个章节
  python main.py --novel-dir ./examples/sample_novel --chapters 1-3 --episode 1
  
  # 批量处理
  python main.py --novel-dir ./examples/sample_novel --batch
  
  # 指定输出格式
  python main.py --novel-dir ./examples/sample_novel --chapters 1-3 --format csv
        """
    )
    
    parser.add_argument(
        "--novel-dir",
        type=str,
        required=True,
        help="小说项目目录（包含 characters.json, toc.json, chapters/）"
    )
    
    parser.add_argument(
        "--chapters",
        type=str,
        help="章节范围（如 '1-3'，表示将第1-3章合并为一集）"
    )
    
    parser.add_argument(
        "--episode",
        type=int,
        help="集数编号"
    )
    
    parser.add_argument(
        "--batch",
        action="store_true",
        help="批量模式（自动将每3章合并为一集，可配合 --chapters-per-episode 或 --words-per-episode 使用）"
    )
    
    parser.add_argument(
        "--chapters-per-episode",
        type=int,
        default=3,
        help="批量模式中每集包含的章节数（默认: 3）"
    )
    
    parser.add_argument(
        "--words-per-episode",
        type=int,
        help="批量模式中每集的目标字符数（优先级高于 chapters-per-episode）"
    )
    
    parser.add_argument(
        "--preserve-paragraphs",
        action="store_true",
        default=True,
        help="保持段落完整性，不会在段落中间截断（默认: 开启）"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="输出目录（默认: ./output）"
    )
    
    parser.add_argument(
        "--format",
        type=str,
        nargs="+",
        choices=["json", "markdown", "csv"],
        default=["json", "markdown", "csv"],
        help="输出格式（默认: 全部）"
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        help="LLM API Key（也可通过环境变量 QIANFAN_API_KEY 设置）"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-v3.1-250821",
        help="LLM 模型名称（默认: deepseek-v3.1-250821）"
    )
    
    args = parser.parse_args()
    
    # 检查小说目录
    novel_dir = Path(args.novel_dir)
    if not novel_dir.exists():
        print(f"❌ 小说目录不存在: {novel_dir}")
        sys.exit(1)
    
    print("🎬 Novel to Drama - 网文转短剧脚本生成器")
    print("=" * 50)
    
    # 1. 加载数据
    print("\n📖 第一步：加载数据...")
    loader = DataLoader(novel_dir)
    print(f"   ✅ 加载完成：{loader.get_chapter_count()} 章")
    print(f"   ✅ 角色数量：{len(loader.get_all_characters())}")
    
    # 2. 初始化模块
    llm_config = config.get_llm_config()
    api_key = args.api_key or llm_config['api_key']
    
    mapper = EpisodeMapper(api_key=api_key, model=args.model)
    generator = ScriptGenerator(api_key=api_key, model=args.model)
    exporter = Exporter(args.output_dir)
    
    # 3. 处理逻辑
    if args.batch:
        # 批量模式
        print("\n🔄 批量模式：自动分组处理...")
        
        # 根据字数或章节数分组
        if args.words_per_episode:
            print(f"   分组依据：按每集 {args.words_per_episode:,} 字符")
            episode_groups = group_by_word_count(loader, args.words_per_episode, args.preserve_paragraphs)
        else:
            print(f"   分组依据：每 {args.chapters_per_episode} 章一集")
            episode_groups = group_by_chapter_count(loader, args.chapters_per_episode)
        
        total_episodes = len(episode_groups)
        episodes = []
        
        for idx, group in enumerate(episode_groups, 1):
            start, end = group['start'], group['end']
            word_count = group.get('word_count', 0)
            
            chapter_info = f"第 {start}-{end} 章" if start != end else f"第 {start} 章"
            if args.words_per_episode:
                print(f"\n📺 处理第 {idx}/{total_episodes} 集（{chapter_info}，约 {word_count:,} 字符）...")
            else:
                print(f"\n📺 处理第 {idx} 集（{chapter_info}）...")
            
            # 生成大纲
            chapters = loader.get_chapters_range(start, end)
            outline = mapper.map_chapters_to_episode(
                chapters,
                loader.get_all_characters(),
                idx,
                f"{start}-{end}"
            )
            
            # 生成剧本
            combined_text = "\n\n".join(chapters)
            script = generator.generate_script(
                outline,
                combined_text,
                loader.get_all_characters()
            )
            
            # 导出
            output_files = exporter.export_all(
                script,
                f"episode_{idx:03d}",
                args.format
            )
            
            episodes.append({
                "episode_num": idx,
                "chapters": f"{start}-{end}",
                "word_count": word_count,
                "output_files": output_files
            })
        
        # 总结
        print("\n" + "=" * 50)
        print("📊 批量处理完成！")
        print(f"   总集数：{len(episodes)}")
        for ep in episodes:
            if args.words_per_episode:
                print(f"   第 {ep['episode_num']} 集（第 {ep['chapters']} 章，约 {ep.get('word_count', 0):,} 字符）")
            else:
                print(f"   第 {ep['episode_num']} 集（第 {ep['chapters']} 章）")
    
    elif args.chapters:
        # 单集模式
        start, end = map(int, args.chapters.split("-"))
        episode_num = args.episode or 1
        
        print(f"\n📺 处理第 {episode_num} 集（第 {start}-{end} 章）...")
        
        # 生成大纲
        print("\n📝 第二步：生成短剧大纲...")
        chapters = loader.get_chapters_range(start, end)
        outline = mapper.map_chapters_to_episode(
            chapters,
            loader.get_all_characters(),
            episode_num,
            f"{start}-{end}"
        )
        print(f"   ✅ 大纲生成完成")
        print(f"      标题：{outline.get('title', '未知')}")
        print(f"      时长：{outline.get('duration_estimate', '未知')}")
        print(f"      反转：{outline.get('reversal_count', 0)} 次")
        
        # 生成剧本
        print("\n🎬 第三步：生成分镜头剧本...")
        combined_text = "\n\n".join(chapters)
        script = generator.generate_script(
            outline,
            combined_text,
            loader.get_all_characters()
        )
        print(f"   ✅ 剧本生成完成")
        print(f"      场景数：{len(script.get('scenes', []))}")
        print(f"      总镜头：{script.get('total_shots', 0)}")
        
        # 导出
        print("\n💾 第四步：导出剧本...")
        output_files = exporter.export_all(
            script,
            f"episode_{episode_num:03d}",
            args.format
        )
        
        print("\n" + "=" * 50)
        print("✅ 处理完成！")
        print(f"   输出文件：")
        for file in output_files:
            print(f"      - {file}")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
