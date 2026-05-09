import { ProgressBar, getTaskStepLabel } from './utils'
import EpisodeCard from '../../components/EpisodeCard'
import type { DramaEpisode } from '../../api/drama'
import type { Chapter } from '../../api/chapter'

interface DramaTabProps {
  dramaEpisodes: DramaEpisode[]
  chapters: Chapter[]
  dramaLoading: boolean
  dramaPlanGenerating: boolean
  batchDramaGenerating: boolean
  generatingDramaEpisodeNum: number | null
  selectedEpisodeIds: Set<string>
  setSelectedEpisodeIds: (v: Set<string>) => void
  activeTask: { id: string; type: string; progress: number; status: string } | null
  onGenerateDramaPlan: () => void
  onGenerateDramaBatch: () => void
  onExportEpisode: (id: string, format: 'json' | 'md' | 'csv') => void
  onUpdateSourceChapters: (id: string, sourceChapters: string) => void
  onUpdateOutline: (id: string, outline: Record<string, any>) => void
  onOpenChapterSelector: (episodeNum: number, defaults: number[]) => void
  onExportEpisodesBatch: (ids: string[], format: 'md' | 'json') => Promise<Blob>
}

export default function DramaTab({
  dramaEpisodes,
  chapters,
  dramaLoading,
  dramaPlanGenerating,
  batchDramaGenerating,
  generatingDramaEpisodeNum,
  selectedEpisodeIds,
  setSelectedEpisodeIds,
  activeTask,
  onGenerateDramaPlan,
  onGenerateDramaBatch,
  onExportEpisode,
  onUpdateSourceChapters,
  onUpdateOutline,
  onOpenChapterSelector,
  onExportEpisodesBatch,
}: DramaTabProps) {
  const parseSourceChapters = (sourceChapters: string | null): number[] => {
    if (!sourceChapters) return []
    const rangeMatch = sourceChapters.match(/第(\d+)-(\d+)章/)
    if (rangeMatch) {
      const start = parseInt(rangeMatch[1], 10)
      const end = parseInt(rangeMatch[2], 10)
      const nums: number[] = []
      for (let i = start; i <= end; i++) nums.push(i)
      return nums
    }
    const singleMatch = sourceChapters.match(/第(\d+)章/)
    if (singleMatch) {
      return [parseInt(singleMatch[1], 10)]
    }
    return sourceChapters
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n))
  }

  return (
    <div className="space-y-4">
      <div className="glass-panel p-5">
        <div className="flex justify-between items-center">
          <h2 className="text-base font-medium text-slate-800">短剧改编</h2>
          <div className="flex items-center space-x-3">
            {dramaEpisodes.length > 0 && (
              <div className="flex flex-col items-end">
                <button
                  onClick={onGenerateDramaBatch}
                  disabled={batchDramaGenerating || !dramaEpisodes.some((ep) => ep.outline_json)}
                  className="btn-primary bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 disabled:hover:translate-y-0"
                >
                  {batchDramaGenerating ? '批量生成中...' : 'AI 批量生成全部脚本'}
                </button>
                {!dramaEpisodes.some((ep) => ep.outline_json) && (
                  <span className="text-[11px] text-slate-400 mt-1">请先生成改编计划</span>
                )}
              </div>
            )}
            <button
              onClick={onGenerateDramaPlan}
              disabled={dramaPlanGenerating}
              className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
            >
              {dramaPlanGenerating ? '生成中...' : 'AI 生成改编计划'}
            </button>
          </div>
        </div>
      </div>
      {activeTask?.type === 'drama_plan' && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}
      {activeTask?.type === 'drama_episode' && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}
      {activeTask?.type === 'drama_batch' && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}

      {dramaLoading ? (
        <p className="text-slate-400 text-sm py-8 text-center">加载中...</p>
      ) : dramaEpisodes.length === 0 ? (
        <div className="glass-panel p-8 text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-indigo-50 flex items-center justify-center">
            <span className="text-xl">🎬</span>
          </div>
          <h3 className="text-sm font-medium text-slate-700 mb-2">还没有短剧改编计划</h3>
          <p className="text-sm text-slate-400 mb-5 max-w-sm mx-auto">
            短剧改编需要两步：先由 AI 分析小说章节并创建分集大纲，再为每集生成分镜头脚本
          </p>
          <div className="flex items-center justify-center space-x-6 text-xs text-slate-400 mb-5">
            <div className="flex flex-col items-center space-y-1">
              <span className="w-6 h-6 rounded-full bg-indigo-50 text-indigo-600 flex items-center justify-center font-medium">1</span>
              <span>生成改编计划</span>
            </div>
            <span className="text-slate-300">→</span>
            <div className="flex flex-col items-center space-y-1">
              <span className="w-6 h-6 rounded-full bg-slate-50 text-slate-400 flex items-center justify-center font-medium">2</span>
              <span>生成各集脚本</span>
            </div>
          </div>
          <button
            onClick={onGenerateDramaPlan}
            disabled={dramaPlanGenerating}
            className="btn-primary disabled:opacity-50"
          >
            {dramaPlanGenerating ? '生成中...' : '开始第一步：生成改编计划'}
          </button>
        </div>
      ) : (
        <>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-3">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={dramaEpisodes.length > 0 && selectedEpisodeIds.size === dramaEpisodes.length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedEpisodeIds(new Set(dramaEpisodes.map((ep) => ep.id)))
                    } else {
                      setSelectedEpisodeIds(new Set())
                    }
                  }}
                  className="rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                />
                <span className="text-xs text-slate-500">全选</span>
              </label>
              {selectedEpisodeIds.size > 0 && (
                <>
                  <button
                    onClick={async () => {
                      try {
                        const blob = await onExportEpisodesBatch(Array.from(selectedEpisodeIds), 'md')
                        const url = window.URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = 'episodes_batch.md'
                        document.body.appendChild(a)
                        a.click()
                        a.remove()
                        window.URL.revokeObjectURL(url)
                        setSelectedEpisodeIds(new Set())
                      } catch (err: any) {
                        // Error handling is done via global toast or parent
                      }
                    }}
                    className="btn-secondary text-[10px] py-1.5 px-3"
                  >
                    导出选中 MD ({selectedEpisodeIds.size})
                  </button>
                  <button
                    onClick={async () => {
                      try {
                        const blob = await onExportEpisodesBatch(Array.from(selectedEpisodeIds), 'json')
                        const url = window.URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = 'episodes_batch.json'
                        document.body.appendChild(a)
                        a.click()
                        a.remove()
                        window.URL.revokeObjectURL(url)
                        setSelectedEpisodeIds(new Set())
                      } catch (err: any) {
                        // Error handling is done via global toast or parent
                      }
                    }}
                    className="btn-secondary text-[10px] py-1.5 px-3"
                  >
                    JSON
                  </button>
                </>
              )}
            </div>
          </div>
          <div className="space-y-4">
            {dramaEpisodes.map((episode, idx) => (
              <EpisodeCard
                key={episode.id}
                episode={episode}
                chapters={chapters.map((c) => ({ id: c.id, chapter_num: c.chapter_num, title: c.title }))}
                prevEpisode={idx > 0 ? dramaEpisodes[idx - 1] : null}
                isGenerating={generatingDramaEpisodeNum === episode.episode_num}
                isSelected={selectedEpisodeIds.has(episode.id)}
                onToggleSelect={() => {
                  const next = new Set(selectedEpisodeIds)
                  if (next.has(episode.id)) {
                    next.delete(episode.id)
                  } else {
                    next.add(episode.id)
                  }
                  setSelectedEpisodeIds(next)
                }}
                onGenerateScript={() =>
                  onOpenChapterSelector(
                    episode.episode_num,
                    parseSourceChapters(episode.source_chapters)
                  )
                }
                onExport={(fmt: 'json' | 'md' | 'csv') => onExportEpisode(episode.id, fmt)}
                onUpdateSourceChapters={(sourceChapters: string) => onUpdateSourceChapters(episode.id, sourceChapters)}
                onUpdateOutline={(outline: Record<string, any>) => onUpdateOutline(episode.id, outline)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
