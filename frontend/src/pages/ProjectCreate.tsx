import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { createProject } from '../api/project'
import { importInspiration } from '../api/inspiration'
import { queryClient } from '../queryClient'
import { DIMENSION_OPTIONS, DIMENSION_LABELS, DEFAULT_RECIPES } from '../constants/blocks'
import {
  BACKGROUND_SYSTEMS,
  GENRE_HARD_BACKGROUND,
  backgroundSystem,
  checkHardConflicts,
  checkSoftWarnings,
  type WritingConfig,
} from '../constants/conflicts'

interface CollapseSectionProps {
  title: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}

function CollapseSection({ title, open, onToggle, children }: CollapseSectionProps) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 text-sm font-medium text-gray-800 hover:bg-gray-100"
      >
        <span>{title}</span>
        <svg
          className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`}
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 8l5 5 5-5" />
        </svg>
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  )
}

interface ChipGroupProps {
  options: string[]
  value: string | string[]
  multi?: boolean
  onChange: (v: string | string[]) => void
  disabledOptions?: string[]
}

function ChipGroup({ options, value, multi = false, onChange, disabledOptions = [] }: ChipGroupProps) {
  const selected = multi ? (value as string[]) : value ? [value as string] : []
  const toggle = (opt: string) => {
    if (multi) {
      const arr = value as string[]
      onChange(arr.includes(opt) ? arr.filter((x) => x !== opt) : [...arr, opt])
    } else {
      onChange(value === opt ? '' : opt)
    }
  }
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const on = selected.includes(opt)
        const disabled = disabledOptions.includes(opt)
        const cls = on
          ? 'border-indigo-600 bg-indigo-600 text-white'
          : disabled
            ? 'border-gray-200 bg-gray-100 text-gray-300 cursor-not-allowed'
            : 'border-gray-300 bg-white text-gray-700 hover:border-indigo-400'
        return (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            disabled={disabled}
            title={disabled ? '该选项与当前选择冲突，不可选' : undefined}
            className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${cls}`}
          >
            {opt}
          </button>
        )
      })}
    </div>
  )
}

interface CustomFields {
  coreSellingPoint: string
  uniqueSetting: string
  characterReq: string
  avoid: string
  freeNote: string
}

interface WritingState {
  coreGenre: string
  background: string[]
  hooks: string[]
  structure: string
  style: string
  audience: string
  castScale: string
  plotDirection: string
}

/** 把前端写作状态映射为与后端 writing_config 同构的检测用 config（缺省维度不出现）。 */
const writingStateToConfig = (s: WritingState): WritingConfig => {
  const c: WritingConfig = {}
  if (s.coreGenre) c.core_genre = s.coreGenre
  if (s.background.length) c.background = s.background
  if (s.hooks.length) c.hook = s.hooks
  if (s.structure) c.structure = s.structure
  if (s.style) c.style = s.style
  if (s.audience) c.audience = s.audience
  if (s.castScale) c.cast_scale = s.castScale
  if (s.plotDirection.trim()) c.plot_direction = s.plotDirection.trim()
  return c
}

function ProjectCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryTopic = searchParams.get('topic') || ''
  const inspiration = {
    note_id: searchParams.get('note_id') || '',
    title: queryTopic,
    summary: searchParams.get('summary') || '',
    likes: Number(searchParams.get('likes') || 0),
    collects: 0,
    author: searchParams.get('author') || '',
    fetched_at: new Date().toISOString(),
  }

  // 基础区
  const [name, setName] = useState(queryTopic)
  const [topic, setTopic] = useState(queryTopic)
  const [plotDirection, setPlotDirection] = useState('')
  const [numChapters, setNumChapters] = useState(20)
  const [wordNumber, setWordNumber] = useState(3000)
  const [storyShape, setStoryShape] = useState<'final' | 'open' | ''>('')
  const [totalChaptersTarget, setTotalChaptersTarget] = useState<number | ''>('')
  const [error, setError] = useState('')

  // 写作设置：核心题材 + 其他 6 维
  const [coreGenre, setCoreGenre] = useState('')
  const [background, setBackground] = useState<string[]>([])
  const [hooks, setHooks] = useState<string[]>([])
  const [structure, setStructure] = useState('')
  const [style, setStyle] = useState('')
  const [audience, setAudience] = useState('')
  const [castScale, setCastScale] = useState('')

  // 自定义设定
  const [custom, setCustom] = useState<CustomFields>({
    coreSellingPoint: '',
    uniqueSetting: '',
    characterReq: '',
    avoid: '',
    freeNote: '',
  })

  // 折叠区开关
  const [showWriting, setShowWriting] = useState(true)
  const [showOtherDims, setShowOtherDims] = useState(true)
  const [showCustom, setShowCustom] = useState(false)

  const setCustomField =
    (field: keyof CustomFields) => (e: React.ChangeEvent<HTMLTextAreaElement>) =>
      setCustom((prev) => ({ ...prev, [field]: e.target.value }))

  /**
   * 统一变更入口：先把「拟变更状态」转成 config 跑硬冲突/软警告检测。
   * - 硬冲突 → 拒绝变更，在顶部提示冲突项；
   * - 软警告 → 弹 confirm 询问是否继续（软冲突不阻断，用户确认后照常应用）。
   */
  const applyWritingState = (next: WritingState): void => {
    // M3：先清空旧 error，避免「硬冲突提示后修改选项→触发软警告→点取消」残留过期错误文案
    setError('')
    const nextConfig = writingStateToConfig(next)
    const hard = checkHardConflicts(nextConfig)
    if (hard.length) {
      setError(hard.join('\n'))
      return
    }
    const soft = checkSoftWarnings(nextConfig)
    if (soft.length) {
      const confirmed = window.confirm(soft.join('\n\n') + '\n\n是否继续？')
      if (!confirmed) return
    }
    setError('')
    setCoreGenre(next.coreGenre)
    setBackground(next.background)
    setHooks(next.hooks)
    setStructure(next.structure)
    setStyle(next.style)
    setAudience(next.audience)
    setCastScale(next.castScale)
  }

  const handleCoreGenreChange = (genre: string) => {
    const recipe = DEFAULT_RECIPES[genre]
    const next: WritingState = recipe
      ? {
          coreGenre: genre,
          background: [recipe.background],
          hooks: [recipe.hook],
          structure: recipe.structure,
          style: recipe.style,
          audience: recipe.audience,
          castScale: recipe.cast_scale,
          plotDirection,
        }
      : { coreGenre: genre, background: [], hooks: [], structure: '', style: '', audience: '', castScale: '', plotDirection }
    applyWritingState(next)
  }

  const handleBackgroundChange = (v: string[]) =>
    applyWritingState({ coreGenre, background: v, hooks, structure, style, audience, castScale, plotDirection })
  const handleHooksChange = (v: string[]) =>
    applyWritingState({ coreGenre, background, hooks: v, structure, style, audience, castScale, plotDirection })
  const handleStructureChange = (v: string) =>
    applyWritingState({ coreGenre, background, hooks, structure: v, style, audience, castScale, plotDirection })
  const handleStyleChange = (v: string) =>
    applyWritingState({ coreGenre, background, hooks, structure, style: v, audience, castScale, plotDirection })
  const handleAudienceChange = (v: string) =>
    applyWritingState({ coreGenre, background, hooks, structure, style, audience: v, castScale, plotDirection })
  const handleCastScaleChange = (v: string) =>
    applyWritingState({ coreGenre, background, hooks, structure, style, audience, castScale: v, plotDirection })

  // 实时检测：硬冲突 / 软警告（含剧情走向关键词 → 触发 plot_vs_setting）
  const hardWarnings = useMemo<string[]>(
    () =>
      checkHardConflicts(
        writingStateToConfig({ coreGenre, background, hooks, structure, style, audience, castScale, plotDirection }),
      ),
    [coreGenre, background, hooks, structure, style, audience, castScale, plotDirection],
  )
  const softWarnings = useMemo<string[]>(
    () =>
      checkSoftWarnings(
        writingStateToConfig({ coreGenre, background, hooks, structure, style, audience, castScale, plotDirection }),
      ),
    [coreGenre, background, hooks, structure, style, audience, castScale, plotDirection],
  )

  // 联动禁用：
  //  - 背景：题材硬禁的世界系置灰 + 跨世界系（除中性山野）禁选
  //  - 结构：精简卡司（独角戏/全员工具人）禁选群像交织
  //  - 规模：结构选了群像交织时，反向禁选精简卡司
  //  - 卖点：金手指系统 × 打脸爽感 互斥禁选
  const disabledBackgroundOptions = useMemo<string[]>(() => {
    const bannedSystems = new Set(coreGenre ? (GENRE_HARD_BACKGROUND[coreGenre] ?? []) : [])
    const selectedNonNeutral = new Set(
      background
        .map((b) => backgroundSystem(b))
        .filter((s): s is string => s !== null && !BACKGROUND_SYSTEMS[s].neutral),
    )
    return DIMENSION_OPTIONS.background.filter((opt) => {
      const sys = backgroundSystem(opt)
      if (!sys) return false
      if (bannedSystems.has(sys)) return true
      if (selectedNonNeutral.size > 0 && !BACKGROUND_SYSTEMS[sys].neutral && !selectedNonNeutral.has(sys)) {
        return true
      }
      return false
    })
  }, [coreGenre, background])

  const disabledStructureOptions = useMemo<string[]>(
    () => (castScale === '独角戏' || castScale === '全员工具人' ? ['群像交织'] : []),
    [castScale],
  )
  const disabledCastOptions = useMemo<string[]>(
    () => (structure === '群像交织' ? ['独角戏', '全员工具人'] : []),
    [structure],
  )
  const disabledHookOptions = useMemo<string[]>(() => {
    const d: string[] = []
    if (hooks.includes('金手指系统')) d.push('打脸爽感')
    if (hooks.includes('打脸爽感')) d.push('金手指系统')
    return d
  }, [hooks])

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      if (inspiration.note_id) {
        try {
          await importInspiration(data.id, { ...inspiration, title: topic || queryTopic })
        } catch (e) {
          console.error('导入灵感失败', e)
        }
      }
      navigate(`/projects/${data.id}`)
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建项目失败')
    },
  })

  const buildWritingConfig = (): Record<string, unknown> => {
    const config: Record<string, unknown> = {}
    if (plotDirection.trim()) config.plot_direction = plotDirection.trim()
    if (coreGenre) config.core_genre = coreGenre
    // 多选维度直接发数组，后端逐项查块注入各选项 prompt_fragment
    if (background.length) config.background = background
    if (hooks.length) config.hook = hooks
    if (structure) config.structure = structure
    if (style) config.style = style
    if (audience) config.audience = audience
    if (castScale) config.cast_scale = castScale

    const customEntries = (
      [
        ['core_selling_point', custom.coreSellingPoint],
        ['unique_setting', custom.uniqueSetting],
        ['character_req', custom.characterReq],
        ['avoid', custom.avoid],
        ['free_note', custom.freeNote],
      ] as [string, string][]
    ).filter(([, v]) => v.trim())
    if (customEntries.length) {
      config.custom = Object.fromEntries(customEntries)
    }
    return config
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    const config = buildWritingConfig()
    // 提交前硬冲突检查：有则阻止提交并展示冲突项
    const hard = checkHardConflicts(config)
    if (hard.length) {
      setError(hard.join('\n'))
      return
    }
    // 提交前软警告确认（含剧情走向×背景 plot_vs_setting）
    const soft = checkSoftWarnings(config)
    if (soft.length) {
      const confirmed = window.confirm(soft.join('\n\n') + '\n\n是否继续？')
      if (!confirmed) return
    }
    if (!storyShape) {
      setError('请选择故事形态（短篇完结 / 连载开篇）')
      return
    }
    if (storyShape === 'open') {
      const m = Number(totalChaptersTarget)
      if (!totalChaptersTarget || !Number.isInteger(m) || m < 10 || m > 1000) {
        setError('全书目标总章数需为 10~1000 的整数')
        return
      }
      if (m <= numChapters) {
        setError('全书目标总章数必须大于章节数')
        return
      }
    }
    mutation.mutate({
      name,
      topic: topic || undefined,
      genre: coreGenre || undefined,
      num_chapters: numChapters,
      word_number: wordNumber,
      story_shape: storyShape || undefined,
      total_chapters_target: storyShape === 'open' ? Number(totalChaptersTarget) || undefined : undefined,
      writing_config: config,
    })
  }

  const inputCls =
    'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'
  const labelCls = 'block text-sm font-medium text-gray-700'

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold text-gray-900">创建项目</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        <div className="bg-white shadow rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* 基础区 */}
            <div>
              <label className={`${labelCls} mb-1 block`}>
                项目名称 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputCls}
                placeholder="请输入项目名称"
                required
              />
            </div>

            <div>
              <label className={`${labelCls} mb-1 block`}>主题</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className={inputCls}
                placeholder="小说主题，如：修真世界、未来都市"
              />
            </div>

            <div>
              <label className={`${labelCls} mb-1 block`}>
                剧情走向
                <span className="ml-2 text-xs font-normal text-gray-400">
                  作为创作意图高优先注入生成
                </span>
              </label>
              <textarea
                value={plotDirection}
                onChange={(e) => setPlotDirection(e.target.value)}
                rows={3}
                className={`${inputCls} resize-y`}
                placeholder="用一两句话描述故事走向，如：主角重生回到高中时代，靠先知优势逆袭人生，并在过程中揭开上一世的真相。"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={`${labelCls} mb-1 block`}>计划章节数</label>
                <input
                  type="number"
                  value={numChapters}
                  onChange={(e) => setNumChapters(Number(e.target.value))}
                  className={inputCls}
                  min={1}
                />
              </div>
              <div>
                <label className={`${labelCls} mb-1 block`}>每章字数</label>
                <input
                  type="number"
                  value={wordNumber}
                  onChange={(e) => setWordNumber(Number(e.target.value))}
                  className={inputCls}
                  min={500}
                  step={500}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">故事形态</label>
              <div className="mt-1 space-y-2">
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="radio"
                    name="storyShape"
                    checked={storyShape === 'final'}
                    onChange={() => setStoryShape('final')}
                    className="accent-indigo-600"
                  />
                  <span>短篇完结（{numChapters || 20} 章即全书结局，情节架构在本章数内闭环）</span>
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="radio"
                    name="storyShape"
                    checked={storyShape === 'open'}
                    onChange={() => setStoryShape('open')}
                    className="accent-indigo-600"
                  />
                  <span>连载开篇（先写 {numChapters || 20} 章看反响，第 {numChapters || 20} 章留钩子，后续可续写）</span>
                </label>
              </div>
            </div>
            {storyShape === 'open' && (
              <div>
                <label className="block text-sm font-medium text-gray-700">全书目标总章数 M</label>
                <input
                  type="number"
                  min={10}
                  max={1000}
                  value={totalChaptersTarget}
                  onChange={(e) => setTotalChaptersTarget(e.target.value === '' ? '' : Number(e.target.value))}
                  placeholder="例如 60"
                  className="mt-1 w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
                <p className="mt-1 text-xs text-amber-600">该数字创建后不可修改，请谨慎填写</p>
              </div>
            )}

            {/* 写作设置折叠区 */}
            <CollapseSection
              title="写作设置（7 维积木）"
              open={showWriting}
              onToggle={() => setShowWriting((v) => !v)}
            >
              <div className="space-y-5">
                <div>
                  <label className={`${labelCls} mb-2 block`}>
                    {DIMENSION_LABELS.core_genre}
                    <span className="ml-2 text-xs font-normal text-gray-400">单选，选中自动带出默认配方</span>
                  </label>
                  <ChipGroup
                    options={DIMENSION_OPTIONS.core_genre}
                    value={coreGenre}
                    onChange={(v) => handleCoreGenreChange(v as string)}
                  />
                  {coreGenre && (
                    <p className="mt-2 text-xs text-indigo-600">
                      已按「{coreGenre}」默认配方填充下列维度，可展开调整
                    </p>
                  )}
                </div>

                <div className="border-t border-gray-100 pt-4">
                  <CollapseSection
                    title="其他维度（可展开调整）"
                    open={showOtherDims}
                    onToggle={() => setShowOtherDims((v) => !v)}
                  >
                    <div className="space-y-5">
                      <div>
                        <label className={`${labelCls} mb-2 block`}>
                          {DIMENSION_LABELS.background}
                          <span className="ml-2 text-xs font-normal text-gray-400">
                            可多选；同世界系可选，跨系禁选（山野中性系除外）
                          </span>
                        </label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.background}
                          value={background}
                          multi
                          disabledOptions={disabledBackgroundOptions}
                          onChange={(v) => handleBackgroundChange(v as string[])}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>
                          {DIMENSION_LABELS.hook}
                          <span className="ml-2 text-xs font-normal text-gray-400">可多选</span>
                        </label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.hook}
                          value={hooks}
                          multi
                          disabledOptions={disabledHookOptions}
                          onChange={(v) => handleHooksChange(v as string[])}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.structure}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.structure}
                          value={structure}
                          disabledOptions={disabledStructureOptions}
                          onChange={(v) => handleStructureChange(v as string)}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.style}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.style}
                          value={style}
                          onChange={(v) => handleStyleChange(v as string)}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.audience}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.audience}
                          value={audience}
                          onChange={(v) => handleAudienceChange(v as string)}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.cast_scale}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.cast_scale}
                          value={castScale}
                          disabledOptions={disabledCastOptions}
                          onChange={(v) => handleCastScaleChange(v as string)}
                        />
                      </div>

                      {hardWarnings.length > 0 && (
                        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                          <p className="text-sm font-medium text-red-800">存在硬冲突，需调整后才能提交：</p>
                          <ul className="mt-1 list-disc list-inside text-sm text-red-700 space-y-1">
                            {hardWarnings.map((w, i) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {softWarnings.length > 0 && (
                        <div className="p-3 bg-amber-50 border border-amber-200 rounded-md">
                          <p className="text-sm font-medium text-amber-800">软警告（可继续，但建议确认）：</p>
                          <ul className="mt-1 list-disc list-inside text-sm text-amber-700 space-y-1">
                            {softWarnings.map((w, i) => (
                              <li key={i}>{w}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </CollapseSection>
                </div>
              </div>
            </CollapseSection>

            {/* 自定义设定折叠区 */}
            <CollapseSection
              title="自定义设定"
              open={showCustom}
              onToggle={() => setShowCustom((v) => !v)}
            >
              <div className="space-y-5">
                <div>
                  <label className={`${labelCls} mb-1 block`}>
                    核心卖点
                    <span className="ml-2 text-xs font-normal text-gray-400">区别于预设套路库的独家卖点</span>
                  </label>
                  <textarea
                    value={custom.coreSellingPoint}
                    onChange={setCustomField('coreSellingPoint')}
                    rows={2}
                    className={`${inputCls} resize-y`}
                    placeholder="一句话概括你的独家卖点，如：反套路流，所有常见套路都被主角一眼识破"
                  />
                </div>

                <div>
                  <label className={`${labelCls} mb-1 block`}>独特设定</label>
                  <textarea
                    value={custom.uniqueSetting}
                    onChange={setCustomField('uniqueSetting')}
                    rows={2}
                    className={`${inputCls} resize-y`}
                    placeholder="世界观/力量体系/时间线等独特设定"
                  />
                </div>

                <div>
                  <label className={`${labelCls} mb-1 block`}>人物要求</label>
                  <textarea
                    value={custom.characterReq}
                    onChange={setCustomField('characterReq')}
                    rows={2}
                    className={`${inputCls} resize-y`}
                    placeholder="对主角/配角的具体要求，如：女主独立强大、反派有血有肉"
                  />
                </div>

                <div>
                  <label className={`${labelCls} mb-1 block`}>避雷</label>
                  <textarea
                    value={custom.avoid}
                    onChange={setCustomField('avoid')}
                    rows={2}
                    className={`${inputCls} resize-y`}
                    placeholder="明确不要写的内容，如：不要狗血误会、不要无脑降智反派"
                  />
                </div>

                <div>
                  <label className={`${labelCls} mb-1 block`}>自由补充</label>
                  <textarea
                    value={custom.freeNote}
                    onChange={setCustomField('freeNote')}
                    rows={2}
                    className={`${inputCls} resize-y`}
                    placeholder="其他任何想让 AI 知道的创作要求"
                  />
                </div>
              </div>
            </CollapseSection>

            <div className="flex justify-end space-x-4">
              <button
                type="button"
                onClick={() => navigate('/projects')}
                className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {mutation.isPending ? '创建中...' : '创建项目'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}

export default ProjectCreate
