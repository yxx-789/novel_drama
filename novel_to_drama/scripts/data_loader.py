"""
数据加载模块
负责读取小说的人设、目录和章节文本
支持 JSON 和 TXT 格式
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class DataLoader:
    """小说数据加载器"""
    
    def __init__(self, novel_dir: str):
        """
        初始化数据加载器
        
        Args:
            novel_dir: 小说项目根目录
        """
        self.novel_dir = Path(novel_dir)
        self.characters: Dict = {}
        self.toc: List[Dict] = []
        self._load_all()
    
    def _load_all(self):
        """加载所有数据"""
        self._load_characters()
        self._load_toc()
    
    def _load_characters(self):
        """加载人物设定（支持 JSON 和 TXT）"""
        # 优先尝试 JSON 格式
        char_file = self.novel_dir / "characters.json"
        if char_file.exists():
            with open(char_file, 'r', encoding='utf-8') as f:
                self.characters = json.load(f)
            return
        
        # 尝试 TXT 格式
        char_file = self.novel_dir / "characters.txt"
        if char_file.exists():
            self.characters = self._parse_characters_txt(char_file)
            return
        
        # 尝试其他可能的文件名
        for filename in ["角色设定.txt", "人设.txt", "人物设定.txt"]:
            char_file = self.novel_dir / filename
            if char_file.exists():
                self.characters = self._parse_characters_txt(char_file)
                return
        
        print(f"⚠️  人物设定文件不存在")
    
    def _parse_characters_txt(self, file_path: Path) -> Dict:
        """
        解析 TXT 格式的角色设定
        
        支持格式：
        1. 分段式：
           【林枫】
           姓名：林枫
           年龄：25
           身份：商业天才
           
        2. 键值式：
           林枫：
             姓名：林枫
             年龄：25
             
        3. 树状格式：
           楚烨：
           ├──物品:
           │ ├──物品名(类型)：描述
           ├──能力
           │ ├──技能名：描述
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        characters = {}
        
        # 检测是否为树状格式（包含 ├── 或 └──）
        if '├──' in content or '└──' in content:
            return self._parse_tree_format_characters_txt(content)
        
        # 方式1：按 【角色名】 分段
        if '【' in content:
            pattern = r'【(.+?)】\n([\s\S]+?)(?=\n【|$)'
            matches = re.findall(pattern, content)
            
            for name, body in matches:
                char_info = self._parse_key_value_block(body)
                characters[name.strip()] = char_info
        
        # 方式2：按 "角色名:" 分段
        elif re.search(r'^[^：\n]+：\n', content, re.MULTILINE):
            pattern = r'^([^：\n]+)：\n([\s\S]+?)(?=^[^：\n]+：\n|$)'
            matches = re.findall(pattern, content, re.MULTILINE)
            
            for name, body in matches:
                char_info = self._parse_key_value_block(body)
                characters[name.strip()] = char_info
        
        # 方式3：整个文件是单个角色
        else:
            char_info = self._parse_key_value_block(content)
            if char_info.get('姓名') or char_info.get('名字'):
                name = char_info.get('姓名') or char_info.get('名字')
                characters[name] = char_info
        
        return characters
    
    def _parse_tree_format_characters_txt(self, content: str) -> Dict:
        """
        解析树状格式的角色设定
        
        格式示例：
        楚烨：
        ├──物品:
        │ ├──系统宿主终端(道具)：红颜系统重置中...
        ├──能力
        │ ├──技能1：基因诱饵(被动-已关闭)：...
        ├──状态
        │ ├──身体状态: 红玫瑰倒刺贯穿心脏...
        ├──主要角色间关系网
        │ ├──沈清冷：确认自己是她的长生药...
        └──触发或加深的事件
            ├──获得系统底层代码芯片：...
        """
        characters = {}
        lines = content.split('\n')
        
        current_char = None
        current_category = None
        
        for line in lines:
            line = line.rstrip()
            if not line.strip():
                continue
            
            # 检测角色名（顶层，无缩进，以冒号结尾）
            if not line.startswith(' ') and not line.startswith('│') and not line.startswith('├') and not line.startswith('└'):
                if '：' in line:
                    char_name = line.split('：')[0].strip()
                    if char_name and not char_name.startswith('├') and not char_name.startswith('└'):
                        current_char = char_name
                        characters[current_char] = {
                            '姓名': current_char,
                            '物品': [],
                            '能力': [],
                            '状态': [],
                            '关系': [],
                            '事件': []
                        }
                        current_category = None
            
            elif current_char:
                # 检测一级分类（├── 或 └──）
                if '├──' in line or '└──' in line:
                    # 提取一级分类名
                    match = re.search(r'[├└]──([^:：]+)[:：]?', line)
                    if match:
                        category_name = match.group(1).strip()
                        # 映射到标准分类
                        if '物品' in category_name:
                            current_category = '物品'
                        elif '能力' in category_name or '技能' in category_name:
                            current_category = '能力'
                        elif '状态' in category_name:
                            current_category = '状态'
                        elif '关系' in category_name:
                            current_category = '关系'
                        elif '事件' in category_name:
                            current_category = '事件'
                
                # 检测二级项目（│ ├── 或 │ └──）
                elif ('│' in line and ('├──' in line or '└──' in line)) or \
                     ('├──' in line or '└──' in line):
                    # 提取项目名称和描述
                    match = re.search(r'[├└]──(.+?)[：:]\s*(.+)', line)
                    if match and current_category:
                        item_name = match.group(1).strip()
                        item_desc = match.group(2).strip()
                        
                        # 添加到对应分类
                        if current_category in characters[current_char]:
                            characters[current_char][current_category].append({
                                '名称': item_name,
                                '描述': item_desc
                            })
        
        # 为每个角色生成摘要信息
        for char_name, char_info in characters.items():
            # 提取关键身份
            identities = []
            for item in char_info.get('能力', []):
                if '身份' in item.get('名称', '') or '宿主' in item.get('名称', ''):
                    identities.append(item.get('描述', ''))
            
            if identities:
                char_info['身份'] = '、'.join(identities[:3])
            
            # 提取核心状态
            states = []
            for item in char_info.get('状态', []):
                states.append(item.get('描述', ''))
            
            if states:
                char_info['当前状态'] = '；'.join(states[:2])
        
        return characters
    
    def _parse_key_value_block(self, text: str) -> Dict:
        """
        解析键值对文本块
        
        支持：
        - 键：值
        - 键：值（多行）
        """
        result = {}
        lines = text.strip().split('\n')
        
        current_key = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测键值对
            if '：' in line or ':' in line:
                # 保存上一个键值对
                if current_key:
                    result[current_key] = '\n'.join(current_value).strip()
                
                # 解析新的键值对
                parts = re.split(r'[：:]', line, 1)
                current_key = parts[0].strip()
                current_value = [parts[1].strip()] if len(parts) > 1 else []
            else:
                # 继续上一个值
                if current_key:
                    current_value.append(line)
        
        # 保存最后一个键值对
        if current_key:
            result[current_key] = '\n'.join(current_value).strip()
        
        return result
    
    def _load_toc(self):
        """加载目录（支持 JSON 和 TXT）"""
        # 优先尝试 JSON 格式
        toc_file = self.novel_dir / "toc.json"
        if toc_file.exists():
            with open(toc_file, 'r', encoding='utf-8') as f:
                self.toc = json.load(f)
            return
        
        # 尝试 TXT 格式
        toc_file = self.novel_dir / "toc.txt"
        if toc_file.exists():
            self.toc = self._parse_toc_txt(toc_file)
            return
        
        # 尝试其他可能的文件名
        for filename in ["目录.txt", "章节目录.txt"]:
            toc_file = self.novel_dir / filename
            if toc_file.exists():
                self.toc = self._parse_toc_txt(toc_file)
                return
        
        # 如果都没有，尝试根据 chapters 目录自动生成
        chapters_dir = self.novel_dir / "chapters"
        if chapters_dir.exists():
            self.toc = self._auto_generate_toc(chapters_dir)
        
        if not self.toc:
            print(f"⚠️  目录文件不存在")
    
    def _parse_toc_txt(self, file_path: Path) -> List[Dict]:
        """
        解析 TXT 格式的目录
        
        支持格式：
        1. 第1章 标题
           第2章 标题
        
        2. 第一章 标题
           第二章 标题
        
        3. 1. 标题
           2. 标题
        
        4. 纯标题（自动编号）
           标题1
           标题2
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        toc = []
        chapter_num = 0
        
        for line in lines:
            # 格式1：第N章 标题
            match = re.match(r'第(\d+)章\s+(.+)', line)
            if match:
                toc.append({
                    "chapter": int(match.group(1)),
                    "title": match.group(2).strip()
                })
                continue
            
            # 格式2：第X章 标题（中文数字）
            match = re.match(r'第([一二三四五六七八九十百千]+)章\s+(.+)', line)
            if match:
                chapter_num = self._chinese_to_number(match.group(1))
                toc.append({
                    "chapter": chapter_num,
                    "title": match.group(2).strip()
                })
                continue
            
            # 格式3：数字. 标题
            match = re.match(r'(\d+)\.\s*(.+)', line)
            if match:
                toc.append({
                    "chapter": int(match.group(1)),
                    "title": match.group(2).strip()
                })
                continue
            
            # 格式4：纯标题（自动编号）
            chapter_num += 1
            toc.append({
                "chapter": chapter_num,
                "title": line
            })
        
        return toc
    
    def _chinese_to_number(self, chinese: str) -> int:
        """中文数字转阿拉伯数字"""
        chinese_map = {
            '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '十': 10, '百': 100, '千': 1000
        }
        
        result = 0
        temp = 0
        
        for char in chinese:
            if char in chinese_map:
                num = chinese_map[char]
                if num >= 10:
                    if temp == 0:
                        temp = 1
                    result += temp * num
                    temp = 0
                else:
                    temp = num
        
        result += temp
        return result
    
    def _auto_generate_toc(self, chapters_dir: Path) -> List[Dict]:
        """根据 chapters 目录自动生成目录"""
        toc = []
        
        chapter_files = sorted(chapters_dir.glob("chapter_*.txt"))
        
        for i, file_path in enumerate(chapter_files, 1):
            # 尝试从文件内容提取标题
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    # 如果第一行是标题格式
                    if first_line and len(first_line) < 50:
                        title = first_line
                    else:
                        title = f"第{i}章"
            except:
                title = f"第{i}章"
            
            toc.append({
                "chapter": i,
                "title": title
            })
        
        return toc
    
    def get_character(self, name: str) -> Optional[Dict]:
        """
        获取指定角色的设定
        
        Args:
            name: 角色名
        
        Returns:
            角色设定字典
        """
        # 支持多种查找方式
        if name in self.characters:
            return self.characters[name]
        
        # 尝试模糊匹配
        for char_name, char_info in self.characters.items():
            if name in char_name or char_name in name:
                return char_info
        
        return None
    
    def get_all_characters(self) -> Dict:
        """获取所有角色设定"""
        return self.characters
    
    def get_chapter_count(self) -> int:
        """获取章节数量"""
        return len(self.toc)
    
    def get_chapter(self, chapter_num: int) -> Optional[str]:
        """
        获取指定章节的文本内容
        
        Args:
            chapter_num: 章节编号（从 1 开始）
        
        Returns:
            章节文本内容
        """
        if chapter_num < 1 or chapter_num > len(self.toc):
            print(f"❌ 章节编号超出范围: {chapter_num}")
            return None
        
        # 从目录获取章节信息
        chapter_file = self.novel_dir / "chapters" / f"chapter_{chapter_num}.txt"
        
        if chapter_file.exists():
            with open(chapter_file, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            print(f"❌ 章节文件不存在: {chapter_file}")
            return None
    
    def get_chapter_title(self, chapter_num: int) -> Optional[str]:
        """
        获取章节标题
        
        Args:
            chapter_num: 章节编号（从 1 开始）
        
        Returns:
            章节标题
        """
        if chapter_num < 1 or chapter_num > len(self.toc):
            return None
        
        return self.toc[chapter_num - 1].get("title", f"第{chapter_num}章")
    
    def get_chapters_range(self, start: int, end: int) -> List[str]:
        """
        获取连续多个章节的文本
        
        Args:
            start: 起始章节（从 1 开始）
            end: 结束章节
        
        Returns:
            章节文本列表
        """
        chapters = []
        for i in range(start, end + 1):
            chapter = self.get_chapter(i)
            if chapter:
                chapters.append(chapter)
        return chapters
    
    def get_character_summary(self, names: List[str] = None, max_items: int = 5) -> str:
        """
        获取角色设定摘要（用于 Prompt）
        
        Args:
            names: 角色名列表，None 表示所有角色
            max_items: 每个分类最多显示的项目数（用于树状格式）
        
        Returns:
            格式化的角色设定文本
        """
        if names is None:
            chars = self.characters
        else:
            chars = {name: self.get_character(name) for name in names if self.get_character(name)}
        
        summary_lines = []
        for name, info in chars.items():
            summary_lines.append(f"【{name}】")
            
            if isinstance(info, dict):
                # 检查是否为树状格式（包含物品/能力/状态等列表）
                if any(key in info for key in ['物品', '能力', '状态', '关系', '事件']):
                    # 树状格式：展示关键信息
                    
                    # 基本信息
                    if info.get('姓名'):
                        summary_lines.append(f"  姓名：{info.get('姓名')}")
                    if info.get('身份'):
                        summary_lines.append(f"  身份：{info.get('身份')}")
                    if info.get('当前状态'):
                        summary_lines.append(f"  当前状态：{info.get('当前状态')}")
                    
                    # 物品（只展示前 max_items 个）
                    items = info.get('物品', [])
                    if items:
                        summary_lines.append(f"  关键物品：")
                        for item in items[:max_items]:
                            summary_lines.append(f"    - {item.get('名称', '')}：{item.get('描述', '')[:100]}")
                    
                    # 能力（只展示前 max_items 个）
                    abilities = info.get('能力', [])
                    if abilities:
                        summary_lines.append(f"  核心能力：")
                        for ability in abilities[:max_items]:
                            summary_lines.append(f"    - {ability.get('名称', '')}：{ability.get('描述', '')[:100]}")
                    
                    # 关系（只展示前 max_items 个）
                    relations = info.get('关系', [])
                    if relations:
                        summary_lines.append(f"  重要关系：")
                        for relation in relations[:max_items]:
                            summary_lines.append(f"    - {relation.get('名称', '')}：{relation.get('描述', '')[:100]}")
                    
                    # 状态（只展示前 max_items 个）
                    states = info.get('状态', [])
                    if states:
                        summary_lines.append(f"  当前状态：")
                        for state in states[:max_items]:
                            summary_lines.append(f"    - {state.get('名称', '')}：{state.get('描述', '')[:100]}")
                    
                    # 事件（只展示前 max_items 个）
                    events = info.get('事件', [])
                    if events:
                        summary_lines.append(f"  关键事件：")
                        for event in events[:max_items]:
                            summary_lines.append(f"    - {event.get('名称', '')}：{event.get('描述', '')[:100]}")
                else:
                    # 普通格式：展示所有键值对
                    for key, value in info.items():
                        summary_lines.append(f"  {key}: {value}")
            else:
                summary_lines.append(f"  {info}")
            
            summary_lines.append("")
        
        return "\n".join(summary_lines)


# 测试代码
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        novel_dir = sys.argv[1]
    else:
        novel_dir = "./examples/sample_novel"
    
    print(f"📖 测试数据加载: {novel_dir}")
    print("=" * 50)
    
    loader = DataLoader(novel_dir)
    
    print(f"\n✅ 章节总数: {loader.get_chapter_count()}")
    print(f"✅ 角色数量: {len(loader.get_all_characters())}")
    
    print("\n👤 角色设定:")
    print(loader.get_character_summary())
    
    print("\n📚 目录:")
    for i, chapter in enumerate(loader.toc, 1):
        print(f"  第{i}章: {chapter.get('title', '未知')}")
    
    if loader.get_chapter_count() > 0:
        print(f"\n📄 第1章内容预览:")
        chapter_text = loader.get_chapter(1)
        if chapter_text:
            print(f"  长度: {len(chapter_text)} 字符")
            print(f"  前100字: {chapter_text[:100]}...")
