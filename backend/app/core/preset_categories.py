"""预设分类 → 搜索关键词映射（唯一真源，采集器与后端共用）。"""

PRESET_CATEGORIES = [
    {"name": "热门话题", "keywords": ["热门", "热搜", "爆款"]},
    {"name": "小说推荐", "keywords": ["小说推荐", "热门小说", "书荒"]},
    {"name": "短剧", "keywords": ["短剧", "短剧剧本", "微短剧"]},
    {"name": "影视改编", "keywords": ["小说改编", "影视化", "IP 改编"]},
    {"name": "写作技巧", "keywords": ["写作技巧", "写小说", "新手写作"]},
    {"name": "玄幻", "keywords": ["玄幻小说", "玄幻"]},
    {"name": "仙侠修仙", "keywords": ["修仙小说", "仙侠", "长生"]},
    {"name": "都市", "keywords": ["都市小说", "都市脑洞"]},
    {"name": "重生", "keywords": ["重生文", "重生"]},
    {"name": "穿越", "keywords": ["穿越文", "架空历史"]},
    {"name": "历史权谋", "keywords": ["历史小说", "大明", "三国"]},
    {"name": "悬疑灵异", "keywords": ["悬疑小说", "灵异", "惊悚"]},
    {"name": "科幻末世", "keywords": ["科幻小说", "末世", "无限流"]},
    {"name": "系统流", "keywords": ["系统流", "面板流", "签到"]},
    {"name": "高武", "keywords": ["高武", "无敌流"]},
    {"name": "游戏电竞", "keywords": ["电竞小说", "游戏文"]},
    {"name": "军事战争", "keywords": ["军事小说", "军旅"]},
    {"name": "武侠", "keywords": ["武侠小说", "江湖"]},
    {"name": "同人二创", "keywords": ["同人文", "火影同人", "斗罗同人"]},
    {"name": "甜宠", "keywords": ["甜宠文", "甜文"]},
    {"name": "现代言情", "keywords": ["现代言情", "都市言情"]},
    {"name": "古代言情", "keywords": ["古代言情", "古言"]},
    {"name": "豪门总裁", "keywords": ["总裁文", "豪门", "霸总"]},
    {"name": "宫斗宅斗", "keywords": ["宫斗", "宅斗"]},
    {"name": "快穿", "keywords": ["快穿文"]},
    {"name": "娱乐圈", "keywords": ["娱乐圈小说", "顶流"]},
    {"name": "校园青春", "keywords": ["校园小说", "青春"]},
    {"name": "先婚后爱", "keywords": ["先婚后爱"]},
    {"name": "追妻火葬场", "keywords": ["追妻火葬场"]},
    {"name": "真假千金", "keywords": ["真假千金", "千金"]},
    {"name": "萌宝", "keywords": ["萌宝", "团宠", "奶爸"]},
    {"name": "年代文", "keywords": ["年代文", "七零", "八零"]},
]


def get_preset_category_names() -> list[str]:
    return [c["name"] for c in PRESET_CATEGORIES]


def get_keywords(name: str) -> list[str]:
    for c in PRESET_CATEGORIES:
        if c["name"] == name:
            return c["keywords"]
    return []
