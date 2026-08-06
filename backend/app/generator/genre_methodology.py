# genre_methodology.py
# -*- coding: utf-8 -*-
"""
题材化伏笔 / 节奏 / 钩子方法论层（V3 P3-A）。

为每个题材提供一套可执行的写作参数：
- conflict_driver        冲突驱动类型（该题材情节推进的本质引擎）
- foreshadowing_intervals 伏笔回收间距（短线 / 中线 / 长线，单位：章）
- touch_every            长线伏笔每 N 章「碰一下」（提醒存在，不揭示）
- recovery_audit         揭示真相 / 回收大伏笔前是否要求「线索审计」（关键线索必须已出现过）
- hook_preference        章末钩子四断法偏好（决定 / 发现 / 误判 / 代价）
- payoff_note            爽点频率与节奏要点
- opening_arc            开篇弧线

数据来自行业可核实的方法论；12 个核心题材全配。无权威专门方法的题材
以「冲突驱动类型=功能分工推进、节奏无独立体系」作为保守默认，并在注释
标注出处等级（A=行业公认方法论，B=常见实践，C=一般性共识），不允许留空。

关键接口：
- get_genre_methodology(genre) -> dict     未知题材回退 DEFAULT_METHODOLOGY（不报错）
- _render_genre_methodology(genre) -> str  渲染成 2-4 句 prompt 片段
- HOOK_FOUR_BREAKS: list[str]              四断法枚举
"""

# 四断法（马良写作「钩子四断法」）：决定/发现/误判/代价
# 决定 = 主角做了不可撤回的选择；发现 = 对旧事实的新解释；
# 误判 = 读者知道角色正走向错误答案；代价 = 目标刚达成、更大账单出现。
HOOK_FOUR_BREAKS = ["决定", "发现", "误判", "代价"]

# 通用温和默认值：未知题材回退，不报错、不降质（C 级：一般性共识）。
DEFAULT_METHODOLOGY = {
    "conflict_driver": (
        "以人物目标与处境推动情节：目标受阻、选择、小步兑现，"
        "不刻意堆叠危机；冲突服务于人物与关系的发展。"
    ),
    "foreshadowing_intervals": {"short": [8, 15], "mid": [20, 40], "long": [50, 90]},
    "touch_every": [12, 18],
    "recovery_audit": False,
    "hook_preference": ["决定", "发现"],
    "payoff_note": (
        "保持节奏感：每 3-5 章一个明确的进展或小收获，让读者有持续正反馈；"
        "不以强行冲突为爽点，以「愿望达成」为顶点。"
    ),
    "opening_arc": "以人物登场与首个变化开局，逐步展开主线，不急于抛大危机。",
}

GENRE_METHODOLOGY = {
    # ============ 悬疑（A 级：本格/社会派常用「线索-反转」结构） ============
    "悬疑": {
        "conflict_driver": (
            "线索误导+真相反转：伏笔本质是认知反转（首次读为 A，揭示时是 B）；"
            "每一轮揭秘都重新定义此前的解读，驱动读者重读与追更。"
        ),
        "foreshadowing_intervals": {"short": [10, 20], "mid": [30, 50], "long": [50, 100]},
        "touch_every": [20, 30],
        "recovery_audit": True,
        "hook_preference": ["发现", "误判"],
        "payoff_note": (
            "爽点来自「认知被颠覆的一刻」：每 2-4 章一次小反转（误读被纠正、"
            "新线索推翻旧推断），真相揭晓前必须完成线索审计。"
        ),
        "opening_arc": "黄金三章递进：入局→加压→承诺（不三连爆），以反常现场/悬念开局。",
    },
    # ============ 言情（B 级：误会-试探-确定主流节奏） ============
    "言情": {
        "conflict_driver": (
            "双向误会推进：先女主误会解除，再男主误会解除；「各自都对」才扎心，"
            "误会的解开带来情感升级，而非纯事件冲突。"
        ),
        "foreshadowing_intervals": {"short": [5, 10], "mid": [15, 25], "long": [40, 60]},
        "touch_every": [8, 12],
        "recovery_audit": False,
        "hook_preference": ["决定", "误判"],
        "payoff_note": (
            "每 2-3 章一次甜蜜互动/情感张力单元；不以事件爽点为标准，"
            "以「情绪被击中」（一次告白、一次和解、一次回首）为顶点。"
        ),
        "opening_arc": "开局快抛矛盾/误会，建 CP 感（先相遇/重逢，再进入试探）。",
    },
    # ============ 玄幻（A 级：升级流经典循环） ============
    "玄幻": {
        "conflict_driver": (
            "升级循环：总目标分解为小目标（筑基→金丹→元婴），每级延伸矛盾"
            "（为突破丹发愁、为宗门资源争抢），目标推进即情节推进。"
        ),
        "foreshadowing_intervals": {"short": [8, 15], "mid": [25, 40], "long": [60, 100]},
        "touch_every": [15, 20],
        "recovery_audit": False,
        "hook_preference": ["决定", "代价"],
        "payoff_note": (
            "每 10 章一次大战/大突破；小爽点密集（收服、夺宝、打脸），"
            "大奖稀少大奖蓄势；升级要带情绪与检验，不能只报数值。"
        ),
        "opening_arc": "踩泥开局→金手指→第一次小爽点，三章内让主角尝到变强的甜头。",
    },
    # ============ 仙侠（B 级：在玄幻基础上叠加道心/因果） ============
    "仙侠": {
        "conflict_driver": (
            "境界突破与道心磨砺并行：力量提升之外更重「心性成长」——"
            "每一境都伴随执念/因果/情劫的考验，突破是心与力的双重跨越。"
        ),
        "foreshadowing_intervals": {"short": [10, 18], "mid": [30, 45], "long": [70, 120]},
        "touch_every": [18, 25],
        "recovery_audit": False,
        "hook_preference": ["决定", "发现"],
        "payoff_note": (
            "爽点来自「道心坚定的一刻」与境界跨越的大场面（渡劫、剑出鞘、"
            "因果了结）；每 10-15 章一次心境变化或重大突破。"
        ),
        "opening_arc": "平凡/困顿出身→窥见机缘→第一次道心触动，铺陈仙侠世界观底色。",
    },
    # ============ 都市（B 级：现实博弈+逆袭通用节奏） ============
    "都市": {
        "conflict_driver": (
            "现实困境+资源博弈：事业/金钱/权力/情感多线交织，主角在具体"
            "处境（公司、家族、商圈）中借力打力，以小胜换大筹码。"
        ),
        "foreshadowing_intervals": {"short": [8, 15], "mid": [20, 35], "long": [50, 80]},
        "touch_every": [12, 18],
        "recovery_audit": False,
        "hook_preference": ["决定", "误判"],
        "payoff_note": (
            "爽点来自逆袭兑现与打脸时刻：每 5-8 章一个事业/关系里程碑"
            "（项目落地、真相揭穿、地位跃升），日常戏与爽点交替。"
        ),
        "opening_arc": "主角困境开局（落魄/被轻视）→转折或金手指→立下翻身目标。",
    },
    # ============ 科幻（B 级：设定驱动，伏笔偏长线） ============
    "科幻": {
        "conflict_driver": (
            "科技设定推进+个人对抗系统：世界观规则（技术/秩序/文明）是情节引擎，"
            "主角的抉择在宏大设定中产生蝴蝶效应；伏笔多为设定级伏笔。"
        ),
        "foreshadowing_intervals": {"short": [10, 20], "mid": [25, 45], "long": [50, 100]},
        "touch_every": [18, 25],
        "recovery_audit": True,
        "hook_preference": ["发现", "决定"],
        "payoff_note": (
            "爽点来自「设定揭示的一刻」（技术真相、系统漏洞、文明秘密）；"
            "每 6-10 章一次设定级揭示或技术反杀，大设定伏笔回收前线索需齐全。"
        ),
        "opening_arc": "以世界观钩子（异常现象/未解之谜）开局，让读者先被设定吸引。",
    },
    # ============ 奇幻（B 级：传统冒险+势力对抗） ============
    "奇幻": {
        "conflict_driver": (
            "冒险任务链+势力对抗：主角在魔法/异界中沿着任务与宿命推进，"
            "阵营立场与个人情义碰撞产生抉择；章节围绕「前行—受阻—突破」组织。"
        ),
        "foreshadowing_intervals": {"short": [8, 15], "mid": [20, 40], "long": [50, 90]},
        "touch_every": [15, 20],
        "recovery_audit": False,
        "hook_preference": ["决定", "代价"],
        "payoff_note": (
            "爽点来自战斗、夺宝与冒险推进：每 5-10 章一次像样的冒险节点"
            "（遗迹、对决、结盟），宝物与伙伴的获得是持续正反馈。"
        ),
        "opening_arc": "异界/异族引入→身份与使命渐显→第一次冒险，铺陈世界奇观。",
    },
    # ============ 历史（B 级：权谋+大势，考据为底） ============
    "历史": {
        "conflict_driver": (
            "权谋博弈+历史大势推动：主角在既定历史洪流中借势而为，"
            "每一步决策都有代价与连锁反应；「个人 vs 时代」的张力是核心。"
        ),
        "foreshadowing_intervals": {"short": [10, 18], "mid": [25, 40], "long": [50, 80]},
        "touch_every": [15, 20],
        "recovery_audit": True,
        "hook_preference": ["决定", "误判"],
        "payoff_note": (
            "爽点来自权谋翻盘与历史事件的顺势推进：每 6-10 章一次布局兑现"
            "（朝堂翻盘、战局逆转、人心归附）；考据细节是硬质量分。"
        ),
        "opening_arc": "主角入局（穿越/乱世/改革）→立身→埋下第一枚布局棋子。",
    },
    # ============ 武侠（B 级：恩怨情仇+武学成长） ============
    "武侠": {
        "conflict_driver": (
            "恩怨情仇+武学成长：情义、规矩与仇恨交织，主角在快意恩仇中"
            "背负选择；武学进步与人心的转变互为因果。"
        ),
        "foreshadowing_intervals": {"short": [5, 10], "mid": [15, 30], "long": [40, 70]},
        "touch_every": [10, 15],
        "recovery_audit": False,
        "hook_preference": ["决定", "代价"],
        "payoff_note": (
            "爽点来自比武、复仇与侠义之举：每 3-6 章一场像样的较量或抉择，"
            "招式的章法要写实，情感的爆发点到即止。"
        ),
        "opening_arc": "以冲突或身世钩子开局（仇家上门/江湖传闻）→立下行走江湖的目标。",
    },
    # ============ 灵异（B 级：氛围+逐层解密，类悬疑但偏感官） ============
    "灵异": {
        "conflict_driver": (
            "灵异事件驱动+真相追溯：每起事件揭开一层真相，事件本身有解——"
            "氛围与感官压迫之外，读者被「到底怎么回事」牵引追更。"
        ),
        "foreshadowing_intervals": {"short": [10, 20], "mid": [30, 50], "long": [50, 90]},
        "touch_every": [15, 20],
        "recovery_audit": True,
        "hook_preference": ["发现", "误判"],
        "payoff_note": (
            "爽点来自揭秘与氛围反转：每 3-5 章一次异象/揭秘推进，"
            "关键伏笔（身世、诅咒、封印）回收前线索需齐全，忌虎头蛇尾。"
        ),
        "opening_arc": "异常事件开局（异象/遗物/怪谈）→主角被卷入→展开追查。",
    },
    # ============ 军事（B 级：战役任务链+军人成长） ============
    "军事": {
        "conflict_driver": (
            "战役任务链+军人成长：命令与良心、个体与集体的冲突贯穿；"
            "每次行动（战斗/任务/演习）都有明确目标与代价，胜负之外见人性。"
        ),
        "foreshadowing_intervals": {"short": [5, 10], "mid": [15, 25], "long": [40, 60]},
        "touch_every": [8, 12],
        "recovery_audit": False,
        "hook_preference": ["决定", "代价"],
        "payoff_note": (
            "爽点来自战术胜利与战场高光：每 4-7 章一场行动（突袭/防守/"
            "救人），战术要合理，牺牲要沉重；日常训练戏可舒缓调节。"
        ),
        "opening_arc": "战局/入伍/任务开局→首场考验→建立团队与目标。",
    },
    # ============ 体育（B 级：比赛推进+三重压力） ============
    "体育": {
        "conflict_driver": (
            "比赛推进+竞技成长：对手、伤病、心态三重压力循环施压，"
            "主角在训练与赛场上用技术与意志突破自我；每一场都有明确胜负与转折。"
        ),
        "foreshadowing_intervals": {"short": [5, 8], "mid": [12, 20], "long": [30, 50]},
        "touch_every": [6, 10],
        "recovery_audit": False,
        "hook_preference": ["决定", "代价"],
        "payoff_note": (
            "爽点来自比赛高光与训练突破：每 2-4 章一场对局/一次突破，"
            "胜负之外带出成长（心态、技术、团队），忌只报比分。"
        ),
        "opening_arc": "低谷/挑战开局（失利、质疑、伤退）→立下目标→投入训练。",
    },
    # ============ 种田（兼容键：日常流结构下的高频题材；C 级） ============
    "种田": {
        "conflict_driver": (
            "发育变强→回报的正反馈循环：情绪主旋律是「愁」而非「危」，"
            "每一次经营/建设的回报都让日子变好一点点，舒适与希望是追读动力。"
        ),
        "foreshadowing_intervals": {"short": [10, 20], "mid": [30, 50], "long": [60, 90]},
        "touch_every": [15, 25],
        "recovery_audit": False,
        "hook_preference": ["决定"],
        "payoff_note": (
            "爽点来自收获感/正反馈（春耕秋收、打脸亲戚、事业升级、全家团宠）；"
            "节奏分阶段：生存→积累→产业升级→守护传承，忌强行制造危机。"
        ),
        "opening_arc": "轻快进入生活流，忌沉重铺陈；以一个小小转机让日子开始变好。",
    },
}


def get_genre_methodology(genre: str) -> dict:
    """按题材名取方法论参数表；未知 / 空题材回退 DEFAULT_METHODOLOGY，不报错。"""
    if not isinstance(genre, str):
        return DEFAULT_METHODOLOGY
    return GENRE_METHODOLOGY.get(genre.strip(), DEFAULT_METHODOLOGY)


def _render_genre_methodology(genre: str) -> str:
    """把题材方法论渲染成 2-4 句 prompt 片段（伏笔间距 / 爽点节奏 / 冲突驱动 / 钩子偏好）。"""
    m = get_genre_methodology(genre)
    intervals = m.get("foreshadowing_intervals", {}) or {}
    short = intervals.get("short", [8, 15])
    mid = intervals.get("mid", [20, 40])
    long = intervals.get("long", [50, 90])
    touch = m.get("touch_every", [12, 18])
    hook = m.get("hook_preference", ["决定", "发现"])
    audit_note = "揭示大伏笔前须先完成线索审计（关键线索必须已在前面出现过）。" if m.get("recovery_audit") else ""

    parts = [
        f"伏笔回收间距：短线 {short[0]}-{short[1]} 章内回收、中线 {mid[0]}-{mid[1]} 章、"
        f"长线 {long[0]}-{long[1]} 章；长线伏笔每 {touch[0]}-{touch[1]} 章「碰一下」提醒存在即可，不急于揭示。",
        f"冲突驱动：{m.get('conflict_driver', '')}",
    ]
    payoff = m.get("payoff_note")
    if payoff:
        parts.append(f"爽点节奏：{payoff}")
    if audit_note:
        parts.append(audit_note)
    hook_str = "、".join(hook)
    parts.append(f"章末钩子偏好：{hook_str} 优先（四断法：决定/发现/误判/代价），断在变化发生的那一刻，不在章尾总结。")
    return " ".join(parts)


def _render_hook_preference(genre: str) -> str:
    """渲染章末钩子偏好为「发现、误判」式短文本（供 {hook_preference} 占位符）。"""
    m = get_genre_methodology(genre)
    prefs = m.get("hook_preference") or HOOK_FOUR_BREAKS[:2]
    return "、".join(prefs)
