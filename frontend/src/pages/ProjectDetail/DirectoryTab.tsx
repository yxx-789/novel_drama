import { useMemo, useState } from 'react'
import { ProgressBar, getTaskStepLabel } from './utils'
import GuidancePanel from '../../components/GuidancePanel'
import VersionHistory from '../../components/VersionHistory'

interface DirectoryTabProps {
  value: string
  onChange: (v: string) => void
  loading: boolean
  saving: boolean
  generating: boolean
  activeTask: { id: string; type: string; progress: number; status: string } | null
  projectId: string
  currentVersion: number
  onSave: () => void
  onGenerate: (guidance?: string) => void
  onExport: () => void
  canContinue: boolean
  totalChaptersTarget: number | null
  numChapters: number
  onContinue: (k: number) => void
}

interface ChapterCard {
  num: number
  title: string
  summary: string
  raw: string
}

export default function DirectoryTab({
  value,
  onChange,
  loading,
  saving,
  generating,
  activeTask,
  projectId,
  currentVersion,
  onSave,
  onGenerate,
  onExport,
  canContinue,
  totalChaptersTarget,
  numChapters,
  onContinue,
}: DirectoryTabProps) {
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
  const [showContinue, setShowContinue] = useState(false)
  const [continueK, setContinueK] = useState<number>(1)

  const chapters = useMemo(() => {
    if (!value.trim()) return []
    const result: ChapterCard[] = []
    const lines = value.split('\n')
    let currentBlock: { num: number; title: string; lines: string[] } | null = null

    const extractSummary = (blockLines: string[]): string => {
      for (const line of blockLines) {
        const clean = line.replace(/^[-\*+]\s*/, '')
        const m = clean.match(/^(?:本章)?简述[：:]\s*(.+)$/)
        if (m) return m[1].trim()
      }
      for (const line of blockLines) {
        const clean = line.replace(/^[-\*+]\s*/, '')
        const m = clean.match(/^(?:本章定位|核心作用)[：:]\s*(.+)$/)
        if (m) return m[1].trim()
      }
      return ''
    }

    for (const rawLine of lines) {
      const trimmed = rawLine.trim()
      if (!trimmed) continue

      const titleMatch = trimmed.match(
        /^(?:目录：)?\*?\*?第\s*(\d+)\s*章\s*[:\-\—\s]+\s*(.+?)(?:\*\*)?$/
      )

      if (titleMatch) {
        if (currentBlock) {
          result.push({
            num: currentBlock.num,
            title: currentBlock.title,
            summary: extractSummary(currentBlock.lines),
            raw: currentBlock.lines.join('\n'),
          })
        }
        currentBlock = {
          num: Number(titleMatch[1]),
          title: titleMatch[2].replace(/\*\*/g, '').trim(),
          lines: [trimmed],
        }
      } else if (currentBlock) {
        currentBlock.lines.push(trimmed)
      }
    }

    if (currentBlock) {
      result.push({
        num: currentBlock.num,
        title: currentBlock.title,
        summary: extractSummary(currentBlock.lines),
        raw: currentBlock.lines.join('\n'),
      })
    }

    return result.sort((a, b) => a.num - b.num)
  }, [value])

  return (
    <div className="flex flex-col h-[calc(100vh-240px)] space-y-3">
      {/* Toolbar */}
      <div className="flex justify-between items-center shrink-0">
        <h2 className="text-base font-serif font-medium text-slate-800">章节目录</h2>
        <div className="flex items-center space-x-3">
          {/* Mode switch */}
          <div className="flex bg-slate-100 rounded-lg p-0.5">
            <button
              onClick={() => setMode('preview')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                mode === 'preview'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              预览
            </button>
            <button
              onClick={() => setMode('edit')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                mode === 'edit'
                  ? 'bg-white text-slate-800 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              编辑
            </button>
          </div>

          {mode === 'edit' && (
            <button
              onClick={onSave}
              disabled={saving}
              className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          )}
          <button
            onClick={onExport}
            className="btn-secondary text-[10px] py-1.5 px-3"
          >
            导出 MD
          </button>
          <button
            onClick={() => onGenerate()}
            disabled={generating}
            className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {generating ? '生成中...' : value.trim() ? '基于当前目录优化生成' : 'AI 生成目录'}
          </button>
          <GuidancePanel
            assetName="目录"
            generating={generating}
            onGenerateWithGuidance={(g) => onGenerate(g)}
          />
          {canContinue && (
            <>
              <button
                onClick={() => { setContinueK(1); setShowContinue(true) }}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg"
              >
                续写
              </button>
              {showContinue && (
                <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
                  <div className="glass-panel p-6 rounded-xl w-96">
                    <h3 className="text-base font-medium text-slate-800 mb-3">续写章节</h3>
                    <p className="text-sm text-gray-600 mb-3">
                      当前已写 {numChapters} 章
                      {totalChaptersTarget ? `，全书目标 ${totalChaptersTarget} 章（剩余 ${totalChaptersTarget - numChapters} 章）` : ''}
                      。本次续写将追加第 {numChapters + 1}~{numChapters + continueK} 章目录（不生成正文），
                      确认目录后可到章节页「AI 批量生成」生成正文。
                    </p>
                    <label className="block text-sm font-medium text-gray-700 mb-1">续写章数 k</label>
                    <input
                      type="number"
                      min={1}
                      max={totalChaptersTarget ? totalChaptersTarget - numChapters : undefined}
                      value={continueK}
                      onChange={(e) => setContinueK(Number(e.target.value))}
                      className="w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                    <div className="mt-4 flex justify-end gap-2">
                      <button onClick={() => setShowContinue(false)} className="px-4 py-2 text-sm text-gray-600">取消</button>
                      <button
                        onClick={() => {
                          if (continueK < 1) return
                          if (totalChaptersTarget && continueK > totalChaptersTarget - numChapters) return
                          setShowContinue(false)
                          onContinue(continueK)
                        }}
                        className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg"
                      >
                        开始续写
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <VersionHistory
            projectId={projectId}
            assetType="directory"
            assetName="目录"
            currentVersion={currentVersion}
          />
        </div>
      </div>

      {activeTask?.type === 'directory' && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}

      {loading ? (
        <p className="text-slate-400 text-xs">加载中...</p>
      ) : (
        <div className="flex-1 min-h-0 bg-white/60 border border-slate-200 rounded-xl overflow-hidden flex flex-col">
          {/* Header bar */}
          <div className="px-3 py-2 border-b border-slate-100 bg-slate-50/50 flex items-center justify-between">
            <span className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">
              {mode === 'preview' ? '预览' : '编辑区'}
            </span>
            {mode === 'preview' && chapters.length > 0 && (
              <span className="text-[10px] text-slate-400">{chapters.length} 章</span>
            )}
          </div>

          {/* Content area */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {mode === 'edit' ? (
              <textarea
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full h-full px-4 py-3 text-sm font-mono leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-100 bg-white/50"
                placeholder="在此编辑章节目录...\n\n格式示例：\n第1章 - 标题\n第2章 - 标题"
              />
            ) : (
              <div className="p-4">
                {chapters.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="w-12 h-12 rounded-xl bg-slate-50 flex items-center justify-center mb-3">
                      <svg className="w-6 h-6 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                      </svg>
                    </div>
                    <p className="text-sm text-slate-500 mb-1">暂无章节目录</p>
                    <p className="text-xs text-slate-400 mb-3">点击「AI 生成目录」或切换到「编辑」模式创建</p>
                    <button
                      onClick={() => setMode('edit')}
                      className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      切换到编辑模式 →
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {chapters.map((ch) => (
                      <div
                        key={ch.num}
                        className="flex items-start gap-3 p-3 rounded-lg border border-slate-200 bg-white hover:border-indigo-200 hover:bg-indigo-50/20 transition-colors"
                      >
                        <div className="shrink-0 w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center">
                          <span className="text-xs font-bold text-indigo-700">{ch.num}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium text-slate-800 truncate">
                            {ch.title}
                          </h4>
                          {ch.summary && (
                            <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">
                              {ch.summary}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
