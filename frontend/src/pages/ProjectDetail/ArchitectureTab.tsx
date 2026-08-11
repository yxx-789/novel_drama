import { useMemo, useState } from 'react'
import { ProgressBar, getTaskStepLabel } from './utils'
import MarkdownPreview from '../../components/MarkdownPreview'
import GuidancePanel from '../../components/GuidancePanel'
import VersionHistory from '../../components/VersionHistory'

interface ArchitectureTabProps {
  value: string
  onChange: (v: string) => void
  characterText: string
  loading: boolean
  saving: boolean
  generating: boolean
  activeTask: { id: string; type: string; progress: number; status: string } | null
  projectId: string
  currentVersion: number
  onSave: () => void
  onGenerate: (guidance?: string) => void
  onExport: () => void
}

interface Section {
  id: string
  title: string
  content: string
}

export default function ArchitectureTab({
  value,
  onChange,
  characterText,
  loading,
  saving,
  generating,
  activeTask,
  projectId,
  currentVersion,
  onSave,
  onGenerate,
  onExport,
}: ArchitectureTabProps) {
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [activeSection, setActiveSection] = useState<string | null>(null)

  const sections = useMemo(() => {
    if (!value.trim()) return []
    const result: Section[] = []
    const lines = value.split('\n')
    let currentTitle = '未命名区块'
    let currentContent: string[] = []
    let sectionId = ''
    let hasFirst = false

    for (const line of lines) {
      const match = line.match(/^#===\s*\d+\)\s*(.+?)\s*===$/)
      if (match) {
        if (hasFirst) {
          result.push({
            id: sectionId,
            title: currentTitle,
            content: currentContent.join('\n').trim(),
          })
        }
        currentTitle = match[1]
        sectionId = `arch-${result.length}`
        currentContent = []
        hasFirst = true
      } else if (hasFirst) {
        currentContent.push(line)
      }
    }

    if (hasFirst) {
      result.push({
        id: sectionId,
        title: currentTitle,
        content: currentContent.join('\n').trim(),
      })
    } else if (value.trim()) {
      result.push({
        id: 'arch-0',
        title: '全部内容',
        content: value.trim(),
      })
    }

    return result
  }, [value])

  const toggleCollapse = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveSection(id)
      setTimeout(() => setActiveSection(null), 1500)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-240px)] space-y-3">
      {/* Toolbar */}
      <div className="flex justify-between items-center shrink-0">
        <h2 className="text-base font-serif font-medium text-slate-800">小说架构</h2>
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
            {generating ? '生成中...' : value.trim() ? '基于当前架构优化生成' : 'AI 生成架构'}
          </button>
          <GuidancePanel
            assetName="架构"
            generating={generating}
            onGenerateWithGuidance={(g) => onGenerate(g)}
          />
          <VersionHistory
            projectId={projectId}
            assetType="architecture"
            assetName="架构"
            currentVersion={currentVersion}
          />
        </div>
      </div>

      {activeTask?.type === 'architecture' && (
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
            {mode === 'preview' && sections.length > 0 && (
              <span className="text-[10px] text-slate-400">{sections.length} 个区块</span>
            )}
          </div>

          {/* Content area */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {mode === 'edit' ? (
              <textarea
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="w-full h-full px-4 py-3 text-sm font-mono leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-100 bg-white/50"
                placeholder="在此编辑小说架构：世界观、主线情节、角色设定...\n\n使用 #=== N) 标题 === 分隔区块"
              />
            ) : (
              <div className="p-4">
                {sections.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="w-12 h-12 rounded-xl bg-slate-50 flex items-center justify-center mb-3">
                      <svg className="w-6 h-6 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <p className="text-sm text-slate-500 mb-1">暂无架构内容</p>
                    <p className="text-xs text-slate-400 mb-3">点击「AI 生成架构」或切换到「编辑」模式创建</p>
                    <button
                      onClick={() => setMode('edit')}
                      className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      切换到编辑模式 →
                    </button>
                  </div>
                ) : (
                  <>
                    {/* Navigation anchors */}
                    {sections.length > 1 && (
                      <div className="flex flex-wrap gap-1.5 mb-4 pb-3 border-b border-slate-100">
                        {sections.map((sec) => (
                          <button
                            key={sec.id}
                            onClick={() => scrollToSection(sec.id)}
                            className={`text-[10px] px-2 py-0.5 rounded-md border transition-colors ${
                              activeSection === sec.id
                                ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                                : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50 hover:border-slate-300'
                            }`}
                          >
                            {sec.title}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Sections */}
                    <div className="space-y-3">
                      {sections.map((sec) => {
                        const isCollapsed = collapsed.has(sec.id)
                        return (
                          <div
                            key={sec.id}
                            id={sec.id}
                            className={`rounded-lg border transition-colors ${
                              activeSection === sec.id
                                ? 'border-indigo-300 bg-indigo-50/30'
                                : 'border-slate-200 bg-white'
                            }`}
                          >
                            <button
                              onClick={() => toggleCollapse(sec.id)}
                              className="w-full flex items-center justify-between px-3 py-2 hover:bg-slate-50/50 transition-colors rounded-t-lg"
                            >
                              <span className="text-sm font-semibold text-slate-700">
                                {sec.title}
                              </span>
                              <svg
                                className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isCollapsed ? '-rotate-90' : ''}`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            </button>
                            {!isCollapsed && (
                              <div className="px-3 pb-3">
                                <MarkdownPreview text={sec.content} />
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>

                    {/* Character Text */}
                    {characterText && (
                      <div className="mt-4 pt-4 border-t border-slate-200">
                        <h3 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wider">人物状态</h3>
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 max-h-64 overflow-y-auto">
                          <MarkdownPreview text={characterText} />
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
