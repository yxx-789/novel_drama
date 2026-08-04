import { useQuery } from '@tanstack/react-query'
import { getAsset } from '../../api/asset'

interface StateChange {
  category: string
  key: string
  field: string
  old: unknown
  new: unknown
}

interface HistoryEntry {
  chapter: number
  changes: StateChange[]
}

interface WorldState {
  genre_template?: string
  characters?: Record<string, Record<string, unknown>>
  events?: Record<string, Record<string, unknown>>
  world?: Record<string, Record<string, unknown>>
  history?: HistoryEntry[]
}

interface WorldStateTabProps {
  projectId: string
  chapters: { id: string; chapter_num: number; title: string | null }[]
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-sm hover:shadow-md transition-shadow">
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/60 rounded-t-lg">
        <h4 className="text-sm font-semibold text-slate-700">{title}</h4>
      </div>
      <div className="p-4 space-y-2">{children}</div>
    </div>
  )
}

function FieldRow({ label, value }: { label: string; value: unknown }) {
  const display = typeof value === 'object' ? JSON.stringify(value) : String(value ?? '-')
  return (
    <div className="flex justify-between items-start gap-3 text-sm">
      <span className="text-slate-500 shrink-0">{label}</span>
      <span className="text-slate-800 text-right break-all">{display}</span>
    </div>
  )
}

function Section({
  title,
  icon,
  items,
}: {
  title: string
  icon: string
  items: Record<string, Record<string, unknown>> | undefined
}) {
  const entries = items ? Object.entries(items) : []
  if (entries.length === 0) return null

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide flex items-center gap-2">
        <span>{icon}</span>
        {title}
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {entries.map(([key, fields]) => (
          <Card key={key} title={key}>
            {Object.entries(fields).map(([f, v]) => (
              <FieldRow key={f} label={f} value={v} />
            ))}
          </Card>
        ))}
      </div>
    </div>
  )
}

async function fetchWorldState(projectId: string) {
  try {
    return await getAsset(projectId, 'world_state')
  } catch (err: any) {
    if (err.response?.status === 404) return null
    throw err
  }
}

export default function WorldStateTab({ projectId, chapters }: WorldStateTabProps) {
  const { data: asset, isLoading, error } = useQuery({
    queryKey: ['asset', projectId, 'world_state'],
    queryFn: () => fetchWorldState(projectId),
  })

  const raw = asset
    ? (asset.content_json ?? (asset.content_text ? JSON.parse(asset.content_text) : null))
    : null
  const state: WorldState | null = raw ?? null

  const hasChapters = chapters.length > 0

  if (isLoading) {
    return <p className="text-slate-400 text-sm">加载中...</p>
  }

  if (error) {
    return <p className="text-rose-500 text-sm">{(error as Error).message || '加载世界状态失败'}</p>
  }

  if (!state) {
    return (
      <div className="text-center py-16">
        <p className="text-slate-400 text-sm">
          {hasChapters ? '世界状态数据尚未创建' : '暂无世界状态数据'}
        </p>
        <p className="text-slate-300 text-xs mt-1 max-w-sm mx-auto">
          {hasChapters
            ? `已生成 ${chapters.length} 章内容，但世界状态是在该功能上线后才开始自动提取的。重新生成任意章节后会自动构建。`
            : '生成章节后会自动构建角色与世界状态追踪'}
        </p>
      </div>
    )
  }

  const hasContent =
    Object.keys(state.characters ?? {}).length > 0 ||
    Object.keys(state.events ?? {}).length > 0 ||
    Object.keys(state.world ?? {}).length > 0

  return (
    <div className="space-y-8">
      {state.genre_template && (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
            模板：{state.genre_template}
          </span>
        </div>
      )}

      {!hasContent ? (
        <div className="text-center py-12">
          <p className="text-slate-400 text-sm">
            {hasChapters ? '世界状态数据为空' : '世界状态结构已初始化，等待章节生成后填充数据'}
          </p>
          <p className="text-slate-300 text-xs mt-1 max-w-sm mx-auto">
            {hasChapters
              ? `已生成 ${chapters.length} 章内容，但未提取到角色/事件/世界设定变更。可能是之前生成的章节未触发提取，重新生成任意章节后会自动更新。`
              : '生成章节后会自动构建角色与世界状态追踪'}
          </p>
        </div>
      ) : (
        <>
          <Section title="角色状态" icon="🧑" items={state.characters} />
          <Section title="事件追踪" icon="📌" items={state.events} />
          <Section title="世界设定" icon="🌍" items={state.world} />
        </>
      )}

      {state.history && state.history.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-slate-800 uppercase tracking-wide flex items-center gap-2">
            <span>📜</span>
            变更历史
          </h3>
          <div className="space-y-3">
            {[...state.history].reverse().map((h, idx) => (
              <div
                key={idx}
                className="bg-white border border-slate-200 rounded-lg shadow-sm p-4"
              >
                <div className="text-xs font-semibold text-indigo-700 mb-2">
                  第 {h.chapter} 章
                </div>
                <ul className="space-y-1.5">
                  {h.changes.map((c, cidx) => (
                    <li key={cidx} className="text-xs text-slate-600 flex items-start gap-2">
                      <span className="shrink-0 mt-0.5">
                        {c.category === 'characters' && '👤'}
                        {c.category === 'events' && '📌'}
                        {c.category === 'world' && '🌍'}
                      </span>
                      <span className="break-all">
                        <span className="font-medium text-slate-800">{c.key}</span>
                        {' · '}
                        <span className="text-slate-500">{c.field}</span>
                        {'  '}
                        <span className="text-slate-400 line-through">{String(c.old ?? '-')}</span>
                        {' → '}
                        <span className="text-emerald-600 font-medium">{String(c.new ?? '-')}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
