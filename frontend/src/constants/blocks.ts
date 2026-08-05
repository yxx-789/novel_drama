/**
 * V3 积木式生成：前端常量（选项集 + 默认配方）。
 *
 * 数据来源与后端 `backend/app/generator/block_library.py` 保持一致（后端库为准）。
 * 前端只需选项名（用于表单渲染）与默认配方（选题材自动带出），
 * 每个选项的完整 prompt_fragment 由后端注入生成 prompt，前端不需要。
 */

export const DIMENSION_LABELS: Record<string, string> = {
  core_genre: '核心题材',
  background: '故事背景',
  hook: '核心卖点',
  structure: '叙事结构',
  style: '文风基调',
  audience: '目标受众',
  cast_scale: '角色规模',
}

export const DIMENSION_OPTIONS: Record<string, string[]> = {
  core_genre: [
    '玄幻', '仙侠', '都市', '科幻', '奇幻', '历史',
    '悬疑', '言情', '武侠', '灵异', '军事', '体育',
  ],
  background: [
    '大陆争霸', '宗门林立', '都市霓虹', '末世废土',
    '星际远征', '王朝庙堂', '山野灵异', '学院青春',
  ],
  hook: [
    '金手指系统', '重生逆袭', '穿越异世', '扮猪吃虎', '打脸爽感', '升级变强',
    '智斗谋略', '情感拉扯', '群像冒险', '真相解谜', '反套路',
  ],
  structure: [
    '单元剧快节奏', '长线连载', '三幕经典', '群像交织',
    '倒叙钩子', '日常流', '升级打怪',
  ],
  style: [
    '热血澎湃', '轻松诙谐', '冷峻写实', '诗意典雅',
    '悬疑紧张', '硬核专业', '温暖治愈', '华丽炫技',
  ],
  audience: [
    '爽文快感', '轻松解压', '硬核烧脑', '文艺情感',
    '全年龄合家欢', '猎奇暗黑', '专业考据',
  ],
  cast_scale: [
    '独角戏', '双主角', '三足鼎立', '小队协作', '群像', '全员工具人',
  ],
}

/**
 * 默认配方：12 个核心题材各一份。
 * 选题材时自动带出 背景/卖点/结构/文风/受众/规模 的默认值。
 * 与后端 DEFAULT_RECIPES 一致。
 */
export const DEFAULT_RECIPES: Record<string, Record<string, string>> = {
  玄幻: {
    core_genre: '玄幻', background: '宗门林立', hook: '金手指系统',
    structure: '升级打怪', style: '热血澎湃', audience: '爽文快感', cast_scale: '独角戏',
  },
  仙侠: {
    core_genre: '仙侠', background: '宗门林立', hook: '重生逆袭',
    structure: '长线连载', style: '诗意典雅', audience: '文艺情感', cast_scale: '小队协作',
  },
  都市: {
    core_genre: '都市', background: '都市霓虹', hook: '打脸爽感',
    structure: '单元剧快节奏', style: '轻松诙谐', audience: '轻松解压', cast_scale: '独角戏',
  },
  科幻: {
    core_genre: '科幻', background: '星际远征', hook: '智斗谋略',
    structure: '三幕经典', style: '硬核专业', audience: '硬核烧脑', cast_scale: '小队协作',
  },
  奇幻: {
    core_genre: '奇幻', background: '大陆争霸', hook: '群像冒险',
    structure: '三幕经典', style: '华丽炫技', audience: '全年龄合家欢', cast_scale: '群像',
  },
  历史: {
    core_genre: '历史', background: '王朝庙堂', hook: '智斗谋略',
    structure: '长线连载', style: '冷峻写实', audience: '专业考据', cast_scale: '三足鼎立',
  },
  悬疑: {
    core_genre: '悬疑', background: '都市霓虹', hook: '真相解谜',
    structure: '倒叙钩子', style: '悬疑紧张', audience: '硬核烧脑', cast_scale: '独角戏',
  },
  言情: {
    core_genre: '言情', background: '都市霓虹', hook: '情感拉扯',
    structure: '日常流', style: '诗意典雅', audience: '文艺情感', cast_scale: '双主角',
  },
  武侠: {
    core_genre: '武侠', background: '大陆争霸', hook: '升级变强',
    structure: '长线连载', style: '冷峻写实', audience: '专业考据', cast_scale: '三足鼎立',
  },
  灵异: {
    core_genre: '灵异', background: '山野灵异', hook: '真相解谜',
    structure: '单元剧快节奏', style: '悬疑紧张', audience: '猎奇暗黑', cast_scale: '独角戏',
  },
  军事: {
    core_genre: '军事', background: '大陆争霸', hook: '群像冒险',
    structure: '长线连载', style: '硬核专业', audience: '专业考据', cast_scale: '小队协作',
  },
  体育: {
    core_genre: '体育', background: '学院青春', hook: '升级变强',
    structure: '单元剧快节奏', style: '热血澎湃', audience: '轻松解压', cast_scale: '小队协作',
  },
}
