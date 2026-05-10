# world_state_templates.py
# -*- coding: utf-8 -*-
"""
世界状态模板：按题材定义需要追踪的状态维度。
LLM 根据模板提取章节文本中的状态变化。
"""

# =============== 通用模板 ===================
GENERIC_TEMPLATE = {
    "description": "通用小说世界状态追踪模板，适用于大部分题材",
    "schema": {
        "characters": {
            "description": "关键角色及其状态",
            "fields": {
                "name": "角色名",
                "status": "当前状态（如：健康/受伤/失踪/死亡）",
                "abilities": "能力/技能列表",
                "items": "持有的关键物品/道具",
                "relationships": "与其他角色的关系（如：盟友/敌对/师徒/恋人）",
                "goals": "当前目标或动机",
                "notes": "其他需要追踪的重要信息",
            },
        },
        "events": {
            "description": "正在推进的关键事件",
            "fields": {
                "name": "事件名",
                "status": "事件状态（如：未开始/进行中/已完成/失败）",
                "deadline": "期限或倒计时（如有）",
                "participants": "参与角色",
                "description": "事件描述",
            },
        },
        "world_rules": {
            "description": "世界规则或设定（发生变化时记录）",
            "fields": {
                "rule_name": "规则名称",
                "description": "规则描述",
                "changed_in_chapter": "在哪一章发生变化",
            },
        },
        "timeline": {
            "description": "世界时间线",
            "fields": {
                "current_time": "当前时间（如：修仙历1024年三月/2024年6月15日）",
                "time_progress": "时间推进说明",
            },
        },
    },
}

# =============== 修仙/玄幻模板 ===================
XIANXIA_TEMPLATE = {
    "description": "修仙/玄幻小说专用状态追踪模板",
    "schema": {
        "characters": {
            "description": "修仙者及其状态",
            "fields": {
                "name": "角色名",
                "realm": "修炼境界（如：练气/筑基/金丹/元婴...）",
                "cultivation_progress": "修炼进度（百分比或阶段描述）",
                "skills": "功法/法术/神通列表",
                "weapons": "武器/法宝",
                "items": "丹药/灵石/材料等",
                "factions": "所属势力/宗门及身份",
                "relationships": "与其他角色的关系",
                "mental_state": "心境状态",
                "physique": "体质/血脉",
                "notes": "其他（如：心魔/因果/气运）",
            },
        },
        "events": {
            "description": "修仙事件",
            "fields": {
                "name": "事件名",
                "event_type": "事件类型（宗门大比/秘境探索/天劫/突破/复仇等）",
                "status": "状态",
                "deadline": "期限（如：宗门大比3个月后/天劫倒计时7天）",
                "participants": "参与角色",
                "rewards": "预期奖励",
                "risks": "潜在风险",
            },
        },
        "world": {
            "description": "修仙世界状态",
            "fields": {
                "current_date": "当前日期（修仙历）",
                "celestial_phenomena": "天象/灵气潮汐/异象",
                "power_balance": "势力格局变化",
                "secret_realms": "秘境开启/关闭状态",
                "rules": "天道规则/法则变化",
            },
        },
    },
}

# =============== 都市/商战模板 ===================
URBAN_TEMPLATE = {
    "description": "都市/商战/系统流小说专用状态追踪模板",
    "schema": {
        "characters": {
            "description": "角色及其社会状态",
            "fields": {
                "name": "角色名",
                "job": "职业/身份",
                "wealth": "财富状况",
                "companies": "公司/产业及持股比例",
                "skills": "技能/能力（如：编程Lv5/格斗Lv3）",
                "social_status": "社会地位/声望",
                "relationships": "人际关系",
                "secrets": "隐藏身份/秘密",
                "notes": "其他",
            },
        },
        "events": {
            "description": "都市事件",
            "fields": {
                "name": "事件名",
                "event_type": "类型（产品发布/商业竞争/合同/比赛/复仇等）",
                "status": "状态",
                "deadline": "期限",
                "participants": "参与方",
                "stakes": "赌注/收益/损失",
            },
        },
        "world": {
            "description": "都市世界状态",
            "fields": {
                "current_date": "当前日期",
                "market_trends": "市场趋势/行业动态",
                "news": "重大新闻（影响剧情）",
                "system_tasks": "系统任务及进度（如适用）",
            },
        },
    },
}


def get_template(genre: str = "") -> dict:
    """根据小说类型返回对应模板"""
    genre_lower = (genre or "").lower()
    if any(k in genre_lower for k in ("修仙", "玄幻", "仙侠", "修真", "武侠", "xianxia", "wuxia", "fantasy")):
        return XIANXIA_TEMPLATE
    if any(k in genre_lower for k in ("都市", "现代", "商战", "系统", "重生", "urban", "modern", "sys")):
        return URBAN_TEMPLATE
    return GENERIC_TEMPLATE
