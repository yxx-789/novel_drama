import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { createProject } from '../api/project'
import { importInspiration } from '../api/inspiration'
import { queryClient } from '../queryClient'
import { DIMENSION_OPTIONS, DIMENSION_LABELS, DEFAULT_RECIPES } from '../constants/blocks'

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
}

function ChipGroup({ options, value, multi = false, onChange }: ChipGroupProps) {
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
        return (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`px-3 py-1.5 rounded-full border text-sm transition-colors ${
              on
                ? 'border-indigo-600 bg-indigo-600 text-white'
                : 'border-gray-300 bg-white text-gray-700 hover:border-indigo-400'
            }`}
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

  const handleCoreGenreChange = (genre: string) => {
    setCoreGenre(genre)
    const recipe = DEFAULT_RECIPES[genre]
    if (recipe) {
      // 选题材自动带出默认配方
      setBackground([recipe.background])
      setHooks([recipe.hook])
      setStructure(recipe.structure)
      setStyle(recipe.style)
      setAudience(recipe.audience)
      setCastScale(recipe.cast_scale)
    } else {
      setBackground([])
      setHooks([])
      setStructure('')
      setStyle('')
      setAudience('')
      setCastScale('')
    }
  }

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
    // 多选维度串成「、」分隔字符串，避免后端 dict key 用 list 导致崩溃
    if (background.length) config.background = background.join('、')
    if (hooks.length) config.hook = hooks.join('、')
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
    mutation.mutate({
      name,
      topic: topic || undefined,
      genre: coreGenre || undefined,
      num_chapters: numChapters,
      word_number: wordNumber,
      writing_config: buildWritingConfig(),
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
                          <span className="ml-2 text-xs font-normal text-gray-400">可多选</span>
                        </label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.background}
                          value={background}
                          multi
                          onChange={(v) => setBackground(v as string[])}
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
                          onChange={(v) => setHooks(v as string[])}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.structure}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.structure}
                          value={structure}
                          onChange={(v) => setStructure(v as string)}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.style}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.style}
                          value={style}
                          onChange={(v) => setStyle(v as string)}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.audience}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.audience}
                          value={audience}
                          onChange={(v) => setAudience(v as string)}
                        />
                      </div>

                      <div>
                        <label className={`${labelCls} mb-2 block`}>{DIMENSION_LABELS.cast_scale}</label>
                        <ChipGroup
                          options={DIMENSION_OPTIONS.cast_scale}
                          value={castScale}
                          onChange={(v) => setCastScale(v as string)}
                        />
                      </div>
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
