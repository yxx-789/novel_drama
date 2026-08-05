/**
 * V3 写作配置冲突规则引擎：前端轻量副本。
 *
 * 与后端 `backend/app/generator/block_library.py` 的规则数据保持一致
 * （后端为准，前端向后端看齐）。前端只需「规则判定」，不注入 prompt 片段。
 * 维度键名与积木值名均用真实积木名（如 cast_scale / structure / background / hook）。
 */

// ----------------------------------------------------------------------
// 8.1 背景世界系分组
// ----------------------------------------------------------------------
export interface BackgroundSystemInfo {
  背景块: string[]
  neutral: boolean
}

export const BACKGROUND_SYSTEMS: Record<string, BackgroundSystemInfo> = {
  古风: { 背景块: ['宗门林立', '王朝庙堂', '大陆争霸'], neutral: false },
  山野: { 背景块: ['山野灵异'], neutral: true }, // 中性：与任意系搭配都不冲突
  现代: { 背景块: ['都市霓虹', '学院青春'], neutral: false },
  未来: { 背景块: ['末世废土', '星际远征'], neutral: false },
}

// ----------------------------------------------------------------------
// 8.2 题材硬禁背景系
// ----------------------------------------------------------------------
export const GENRE_HARD_BACKGROUND: Record<string, string[]> = {
  历史: ['现代', '未来'],
  体育: ['古风', '未来'],
}

// ----------------------------------------------------------------------
// 8.3 硬冲突（跨维度 / 同维度互斥）
// ----------------------------------------------------------------------
export interface HardConflict {
  a_dim: string
  a_value: string
  b_dim: string
  b_value: string
  reason: string
}

export const HARD_CONFLICTS: HardConflict[] = [
  {
    a_dim: 'cast_scale',
    a_value: '独角戏',
    b_dim: 'structure',
    b_value: '群像交织',
    reason: '精简卡司无法承载多线群像结构，请保留其一',
  },
  {
    a_dim: 'cast_scale',
    a_value: '全员工具人',
    b_dim: 'structure',
    b_value: '群像交织',
    reason: '精简卡司无法承载多线群像结构，请保留其一',
  },
  {
    a_dim: 'hook',
    a_value: '金手指系统',
    b_dim: 'hook',
    b_value: '打脸爽感',
    reason: '无敌流主角不存在「被轻视」的真实威胁，打脸套路失去张力，请保留其一',
  },
  {
    a_dim: 'internal_flavor',
    a_value: '娇软治愈',
    b_dim: 'internal_flavor',
    b_value: '女强飒爽',
    reason: '娇软与女强人设相斥，请保留其一',
  },
]

// ----------------------------------------------------------------------
// 8.4 软警告
// （罕见融合 / 卖点错位 / 文风×受众张力 / 文风×题材 / 结构×受众 / 规模×题材 /
//   结构×背景 / 重生×穿越冗余 / 剧情走向×设定 关键词冲突）
// ----------------------------------------------------------------------
export interface PairWarningRule {
  id: string
  kind: 'pair'
  dim_a: string
  dim_b: string
  pairs: [string, string][]
  message: string
}

export interface MismatchWarningRule {
  id: string
  kind: 'mismatch'
  dim: string
  base_dim: string
  mapping: Record<string, string[]>
  message: string
}

export interface BothWarningRule {
  id: string
  kind: 'both'
  dim: string
  values: string[]
  message: string
}

export interface KeywordBackgroundWarningRule {
  id: string
  kind: 'keyword_vs_background'
  dim: string
  background_dim: string
  keywords: Record<string, string>
  message: string
}

export type SoftWarningRule =
  | PairWarningRule
  | MismatchWarningRule
  | BothWarningRule
  | KeywordBackgroundWarningRule

export const SOFT_WARNINGS: SoftWarningRule[] = [
  {
    id: 'genre_x_background_fusion',
    kind: 'pair',
    dim_a: 'core_genre',
    dim_b: 'background',
    pairs: [
      ['仙侠', '末世废土'],
      ['仙侠', '星际远征'],
      ['历史', '星际远征'],
      ['体育', '末世废土'],
      ['武侠', '星际远征'],
      ['都市', '末世废土'],
      ['言情', '末世废土'],
      ['言情', '星际远征'],
    ],
    message: '罕见融合：{a} × {b} 的组合较为罕见，驾驭难度高，建议先确认世界观能自洽。',
  },
  {
    id: 'hook_x_genre_mismatch',
    kind: 'mismatch',
    dim: 'hook',
    base_dim: 'core_genre',
    mapping: {
      情感拉扯: ['军事', '体育', '灵异'],
      真相解谜: ['体育', '玄幻', '仙侠'],
      金手指系统: ['言情', '历史'],
      群像冒险: ['言情', '灵异'],
      升级变强: ['言情'],
      反套路: ['言情', '体育'],
    },
    message: '卖点错位：{a} 卖点在 {b} 题材下较难施展，建议换成更契合题材的卖点。',
  },
  {
    id: 'style_x_audience_tension',
    kind: 'pair',
    dim_a: 'style',
    dim_b: 'audience',
    pairs: [
      ['冷峻写实', '轻松解压'],
      ['悬疑紧张', '轻松解压'],
      ['温暖治愈', '猎奇暗黑'],
      ['热血澎湃', '文艺情感'],
      ['诗意典雅', '爽文快感'],
      ['硬核专业', '文艺情感'],
      ['华丽炫技', '专业考据'],
    ],
    message: '文风与受众张力：{a} 文风与 {b} 受众的阅读期待相左，需在行文上做平衡。',
  },
  {
    id: 'style_x_genre',
    kind: 'pair',
    dim_a: 'style',
    dim_b: 'core_genre',
    pairs: [
      ['冷峻写实', '言情'],
      ['悬疑紧张', '言情'],
      ['温暖治愈', '悬疑'],
      ['温暖治愈', '军事'],
      ['热血澎湃', '言情'],
      ['硬核专业', '言情'],
      ['诗意典雅', '体育'],
    ],
    message: '文风与题材张力：{a} 文风与 {b} 题材的主流调性相左，可能水土不服。',
  },
  {
    id: 'structure_x_audience',
    kind: 'pair',
    dim_a: 'structure',
    dim_b: 'audience',
    pairs: [
      ['日常流', '爽文快感'],
      ['长线连载', '爽文快感'],
      ['日常流', '硬核烧脑'],
    ],
    message: '结构与受众张力：{a} 结构与 {b} 受众的节奏期待相左，可能读起来拖沓或不适。',
  },
  {
    id: 'cast_x_genre',
    kind: 'pair',
    dim_a: 'cast_scale',
    dim_b: 'core_genre',
    pairs: [
      ['群像', '言情'],
      ['群像', '灵异'],
      ['双主角', '体育'],
      ['独角戏', '军事'],
    ],
    message: '规模与题材张力：{a} 卡司规模与 {b} 题材的主流形态相左。',
  },
  {
    id: 'structure_x_background',
    kind: 'pair',
    dim_a: 'structure',
    dim_b: 'background',
    pairs: [
      ['日常流', '星际远征'],
      ['日常流', '末世废土'],
      ['日常流', '大陆争霸'],
      ['倒叙钩子', '山野灵异'],
    ],
    message: '结构与背景张力：{a} 结构与 {b} 背景的氛围相左。',
  },
  {
    id: 'reborn_x_transmigrate',
    kind: 'both',
    dim: 'hook',
    values: ['重生逆袭', '穿越异世'],
    message: '重生×穿越冗余：两个卖点都依赖「先知优势」，功能重叠，建议保留其一。',
  },
  {
    id: 'plot_vs_setting',
    kind: 'keyword_vs_background',
    dim: 'plot_direction',
    background_dim: 'background',
    keywords: {
      现代: '现代',
      都市: '现代',
      校园: '现代',
      学院: '现代',
      星际: '未来',
      末世: '未来',
      废土: '未来',
      古代: '古风',
      王朝: '古风',
      宗门: '古风',
      武侠: '古风',
      江湖: '古风',
      山村: '山野',
      乡村: '山野',
      民俗: '山野',
    },
    message:
      '剧情走向冲突：剧情涉及「{keywords}」类设定，与当前所选背景（{background}）不一致，请确认是刻意设计。',
  },
]

// ----------------------------------------------------------------------
// 检测辅助
// ----------------------------------------------------------------------
export type WritingConfig = Record<string, unknown>

function configValues(config: WritingConfig, dim: string): string[] {
  const v = config[dim]
  if (v === undefined || v === null) return []
  if (Array.isArray(v)) return v.filter((x): x is string => typeof x === 'string')
  return typeof v === 'string' ? [v] : []
}

function configHas(config: WritingConfig, dim: string, value: string): boolean {
  return configValues(config, dim).includes(value)
}

export function backgroundSystem(bg: string): string | null {
  for (const [sys, info] of Object.entries(BACKGROUND_SYSTEMS)) {
    if (info.背景块.includes(bg)) return sys
  }
  return null
}

function dedupe(items: string[]): string[] {
  return Array.from(new Set(items))
}

function fill(message: string, vars: Record<string, string>): string {
  return Object.entries(vars).reduce((acc, [k, v]) => acc.split(`{${k}}`).join(v), message)
}

// ----------------------------------------------------------------------
// 检测函数
// ----------------------------------------------------------------------
/** 硬冲突列表（空 = 无冲突）。覆盖：背景跨系、题材×背景系、规模×结构、卖点互斥。 */
export function checkHardConflicts(config: WritingConfig): string[] {
  if (!config) return []
  const hard: string[] = []

  // (1) 背景跨系：同一背景多选时，非中性世界系之间不能并存
  const bgValues = configValues(config, 'background')
  if (bgValues.length >= 2) {
    const systemBlocks: Record<string, string[]> = {}
    for (const bg of bgValues) {
      const sys = backgroundSystem(bg)
      if (sys) {
        if (!systemBlocks[sys]) systemBlocks[sys] = []
        systemBlocks[sys].push(bg)
      }
    }
    const nonNeutral = Object.keys(systemBlocks).filter((s) => !BACKGROUND_SYSTEMS[s].neutral)
    if (nonNeutral.length > 1) {
      const parts = [...nonNeutral]
        .sort()
        .map((s) => `${s}（${systemBlocks[s].join('、')}）`)
      hard.push(`背景跨系冲突：${parts.join('、')} 属于不同世界系，不能同时选择（山野中性系除外）。`)
    }
  }

  // (2) 题材 × 背景系（历史禁现代/未来；体育禁古风/未来）
  for (const genre of configValues(config, 'core_genre')) {
    const banned = GENRE_HARD_BACKGROUND[genre] ?? []
    if (!banned.length) continue
    for (const bg of bgValues) {
      const sys = backgroundSystem(bg)
      if (sys && banned.includes(sys)) {
        hard.push(`题材硬冲突：${genre} 题材不兼容${sys}系背景「${bg}」。`)
      }
    }
  }

  // (3) 规模×结构 / 卖点互斥（含内部风味互斥，前端不暴露 internal_flavor，数据保留对齐后端）
  for (const rule of HARD_CONFLICTS) {
    if (configHas(config, rule.a_dim, rule.a_value) && configHas(config, rule.b_dim, rule.b_value)) {
      hard.push(`硬冲突：${rule.a_value} × ${rule.b_value} —— ${rule.reason}`)
    }
  }

  return dedupe(hard)
}

/** 软警告列表（空 = 无提示）。覆盖：罕见融合 / 卖点错位 / 文风×受众 / 文风×题材 / 结构×受众 / 规模×题材 / 结构×背景 / 重生×穿越冗余 / 剧情走向×设定。 */
export function checkSoftWarnings(config: WritingConfig): string[] {
  if (!config) return []
  const soft: string[] = []

  for (const rule of SOFT_WARNINGS) {
    if (rule.kind === 'pair') {
      const aVals = configValues(config, rule.dim_a)
      const bVals = configValues(config, rule.dim_b)
      for (const [a, b] of rule.pairs) {
        if (aVals.includes(a) && bVals.includes(b)) {
          soft.push(fill(rule.message, { a, b }))
        }
      }
    } else if (rule.kind === 'mismatch') {
      const dimVals = configValues(config, rule.dim)
      const baseVals = configValues(config, rule.base_dim)
      for (const [dimVal, badBases] of Object.entries(rule.mapping)) {
        if (dimVals.includes(dimVal)) {
          for (const base of badBases) {
            if (baseVals.includes(base)) soft.push(fill(rule.message, { a: dimVal, b: base }))
          }
        }
      }
    } else if (rule.kind === 'both') {
      const vals = configValues(config, rule.dim)
      if (rule.values.every((v) => vals.includes(v))) soft.push(rule.message)
    } else if (rule.kind === 'keyword_vs_background') {
      const text = config[rule.dim]
      const bgValues = configValues(config, rule.background_dim)
      if (typeof text === 'string' && text.trim() && bgValues.length) {
        const matchedKeywords = Object.keys(rule.keywords).filter((kw) => text.includes(kw))
        // 逐背景块判定（山野中性豁免不全局生效）：
        // 只有「与关键词所在世界系一致的背景块」一致豁免；被关键词命中的非山野块仍提示。
        const conflicts: Record<string, string[]> = {}
        for (const bg of bgValues) {
          const sys = backgroundSystem(bg)
          if (!sys) continue
          for (const kw of matchedKeywords) {
            const kwSys = rule.keywords[kw]
            if (kwSys === sys) continue // 该背景块与剧情走向一致
            if (sys === '山野') continue // 山野为中性系，与任意剧情走向都不冲突
            if (!conflicts[bg]) conflicts[bg] = []
            conflicts[bg].push(kw)
          }
        }
        for (const [bg, kws] of Object.entries(conflicts)) {
          soft.push(fill(rule.message, { keywords: kws.join('、'), background: bg }))
        }
      }
    }
  }

  return dedupe(soft)
}
