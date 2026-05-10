import { useEffect, useRef, useCallback } from 'react'
import { ProgressBar, getTaskStepLabel, statusBadge } from './utils'
import type { Chapter, CreateChapterRequest } from '../../api/chapter'

interface ChaptersTabProps {
  chapters: Chapter[]
  directoryText: string
  showAddChapter: boolean
  setShowAddChapter: (v: boolean) => void
  editingChapterId: string | null
  setEditingChapterId: (v: string | null) => void
  generatingChapterNum: number | null
  batchGenerating: boolean
  chapterForm: CreateChapterRequest
  setChapterForm: (v: CreateChapterRequest) => void
  chapterSearchQuery: string
  setChapterSearchQuery: (v: string) => void
  selectedChapterIds: Set<string>
  setSelectedChapterIds: (v: Set<string>) => void
  activeTask: { id: string; type: string; progress: number; status: string } | null
  setDirty: (v: boolean) => void
  onAddChapter: () => void
  onUpdateChapter: (id: string) => void
  onDeleteChapter: (id: string) => void
  onGenerateChapter: (num: number) => void
  onGenerateBatch: () => void
  onExport: () => void
  onExportBatch: (ids: string[]) => void
}

export default function ChaptersTab({
  chapters,
  directoryText,
  showAddChapter,
  setShowAddChapter,
  editingChapterId,
  setEditingChapterId,
  generatingChapterNum,
  batchGenerating,
  chapterForm,
  setChapterForm,
  chapterSearchQuery,
  setChapterSearchQuery,
  selectedChapterIds,
  setSelectedChapterIds,
  activeTask,
  setDirty,
  onAddChapter,
  onUpdateChapter,
  onDeleteChapter,
  onGenerateChapter,
  onGenerateBatch,
  onExport,
  onExportBatch,
}: ChaptersTabProps) {
  const draftRef = useRef<HTMLTextAreaElement>(null)

  const filteredChapters = chapters
    .filter((c) => {
      if (!chapterSearchQuery.trim()) return true
      const q = chapterSearchQuery.toLowerCase()
      return (
        c.title?.toLowerCase().includes(q) ||
        c.outline?.toLowerCase().includes(q) ||
        c.draft?.toLowerCase().includes(q) ||
        String(c.chapter_num).includes(q)
      )
    })
    .sort((a, b) => a.chapter_num - b.chapter_num)

  const selectedChapter = chapters.find((c) => c.id === editingChapterId)

  const isEditing = !!editingChapterId || showAddChapter

  const startEditChapter = useCallback((chapter: Chapter) => {
    setShowAddChapter(false)
    setEditingChapterId(chapter.id)
    setDirty(true)
    setChapterForm({
      chapter_num: chapter.chapter_num,
      title: chapter.title,
      outline: chapter.outline || '',
      draft: chapter.draft || '',
      finalized_text: chapter.finalized_text || '',
      status: chapter.status,
    })
  }, [setShowAddChapter, setEditingChapterId, setDirty, setChapterForm])

  const startCreateChapter = useCallback(() => {
    setEditingChapterId(null)
    setShowAddChapter(true)
    setDirty(true)
    setChapterForm({
      chapter_num: chapters.length + 1,
      title: '',
      outline: '',
      draft: '',
      finalized_text: '',
      status: 'draft',
    })
  }, [chapters.length, setEditingChapterId, setShowAddChapter, setDirty, setChapterForm])

  const handleCancel = useCallback(() => {
    setShowAddChapter(false)
    setEditingChapterId(null)
    setDirty(false)
    setChapterForm({
      chapter_num: chapters.length + 1,
      title: '',
      outline: '',
      draft: '',
      finalized_text: '',
      status: 'draft',
    })
  }, [chapters.length, setShowAddChapter, setEditingChapterId, setDirty, setChapterForm])

  const handleSave = useCallback(() => {
    if (showAddChapter) {
      onAddChapter()
    } else if (editingChapterId) {
      onUpdateChapter(editingChapterId)
    }
  }, [showAddChapter, editingChapterId, onAddChapter, onUpdateChapter])

  // Auto-focus draft textarea when entering edit mode
  useEffect(() => {
    if (isEditing && draftRef.current) {
      draftRef.current.focus()
    }
  }, [editingChapterId, showAddChapter, isEditing])

  // Keyboard shortcut: Ctrl/Cmd + S to save
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        if (isEditing) handleSave()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isEditing, handleSave])

  const wordCount = (chapterForm.draft || '').length

  return (
    <div className="flex h-[calc(100vh-180px)] gap-4">
      {/* Left sidebar: Chapter list */}
      <div className="w-[280px] flex flex-col bg-white/60 border border-slate-200 rounded-xl overflow-hidden">
        {/* Header */}
        <div className="p-3 border-b border-slate-100 space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">章节</h2>
            <span className="text-xs text-slate-400">{chapters.length} 章</span>
          </div>

          {/* Search */}
          <div className="relative">
            <svg className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="搜索..."
              value={chapterSearchQuery}
              onChange={(e) => setChapterSearchQuery(e.target.value)}
              className="w-full pl-7 pr-2 py-1.5 text-xs border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-1.5">
            <button
              onClick={onExport}
              className="flex-1 px-2 py-1 text-[10px] bg-slate-50 text-slate-600 rounded border border-slate-200 hover:bg-slate-100 transition-colors"
            >
              导出
            </button>
          </div>

          {/* Batch export */}
          {selectedChapterIds.size > 0 && (
            <button
              onClick={() => onExportBatch(Array.from(selectedChapterIds))}
              className="w-full px-2 py-1 text-[10px] bg-indigo-50 text-indigo-700 rounded border border-indigo-200 hover:bg-indigo-100 transition-colors"
            >
              导出选中 ({selectedChapterIds.size})
            </button>
          )}

          {/* Progress */}
          {(activeTask?.type === 'chapter' || activeTask?.type === 'batch_chapters') && (
            <ProgressBar
              progress={activeTask.progress}
              label={getTaskStepLabel(activeTask.type, activeTask.progress)}
            />
          )}

          {/* Directory warning */}
          {!directoryText && (
            <p className="text-[10px] text-amber-600 bg-amber-50 px-2 py-1 rounded">
              请先生成目录
            </p>
          )}
        </div>

        {/* Chapter list */}
        <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
          {chapters.length > 0 && (
            <div className="flex items-center justify-between px-2 py-1 mb-1">
              <label className="flex items-center gap-1.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={selectedChapterIds.size === chapters.length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedChapterIds(new Set(chapters.map((c) => c.id)))
                    } else {
                      setSelectedChapterIds(new Set())
                    }
                  }}
                  className="w-3.5 h-3.5 rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                />
                <span className="text-[10px] text-slate-500">全选</span>
              </label>
              <button
                onClick={onGenerateBatch}
                disabled={!directoryText || batchGenerating}
                title={!directoryText ? '请先生成章节目录' : ''}
                className="px-2 py-0.5 text-[10px] bg-emerald-50 text-emerald-700 rounded border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
              >
                {batchGenerating ? '生成中...' : 'AI 批量生成'}
              </button>
            </div>
          )}
          {filteredChapters.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-4">
              {chapterSearchQuery ? '无匹配章节' : '暂无章节'}
            </p>
          ) : (
            filteredChapters.map((chapter) => {
              const isSelected = editingChapterId === chapter.id
              return (
                <div
                  key={chapter.id}
                  onClick={() => startEditChapter(chapter)}
                  className={`group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-indigo-50 border border-indigo-200'
                      : 'hover:bg-slate-50 border border-transparent'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedChapterIds.has(chapter.id)}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => {
                      const next = new Set(selectedChapterIds)
                      if (e.target.checked) {
                        next.add(chapter.id)
                      } else {
                        next.delete(chapter.id)
                      }
                      setSelectedChapterIds(next)
                    }}
                    className="shrink-0 w-3.5 h-3.5 rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] text-slate-400 shrink-0">第{chapter.chapter_num}章</span>
                      <span className={`text-xs font-medium truncate ${isSelected ? 'text-indigo-700' : 'text-slate-700'}`}>
                        {chapter.title || '未命名'}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {statusBadge(chapter.status)}
                      {chapter.draft && (
                        <span className="text-[10px] text-slate-400">
                          {(chapter.draft.length / 1000).toFixed(1)}k 字
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onGenerateChapter(chapter.chapter_num)
                    }}
                    disabled={!directoryText || generatingChapterNum === chapter.chapter_num}
                    className="shrink-0 text-[10px] text-emerald-600 hover:text-emerald-700 disabled:opacity-50 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {generatingChapterNum === chapter.chapter_num ? '...' : 'AI'}
                  </button>
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-2 border-t border-slate-100">
          <button
            onClick={startCreateChapter}
            className="w-full px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded-md hover:bg-indigo-700 transition-colors"
          >
            + 新建章节
          </button>
        </div>
      </div>

      {/* Right panel: Editor */}
      <div className="flex-1 flex flex-col bg-white/60 border border-slate-200 rounded-xl overflow-hidden">
        {!isEditing ? (
          /* Empty state */
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
            <div className="w-16 h-16 rounded-2xl bg-slate-50 flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h3 className="text-sm font-medium text-slate-700 mb-1">选择或创建章节</h3>
            <p className="text-xs text-slate-400 max-w-xs">
              点击左侧章节开始编辑，或使用「新建章节」按钮创建新章节
            </p>
          </div>
        ) : (
          <>
            {/* Editor toolbar */}
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-3 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 shrink-0">
                    {showAddChapter ? '新建' : `第${chapterForm.chapter_num}章`}
                  </span>
                  <input
                    type="text"
                    value={chapterForm.title || ''}
                    onChange={(e) => {
                      setChapterForm({ ...chapterForm, title: e.target.value })
                      setDirty(true)
                    }}
                    placeholder="章节标题..."
                    className="flex-1 min-w-[200px] text-sm font-semibold text-slate-800 bg-transparent border-b border-transparent hover:border-slate-200 focus:border-indigo-300 focus:outline-none px-1 py-0.5 transition-colors"
                  />
                </div>
                <select
                  value={chapterForm.status}
                  onChange={(e) => {
                    setChapterForm({ ...chapterForm, status: e.target.value as any })
                    setDirty(true)
                  }}
                  className="text-xs px-2 py-1 border border-slate-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="draft">草稿</option>
                  <option value="draft_generated">已生成</option>
                  <option value="generating">生成中</option>
                  <option value="finalized">已终稿</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                {!showAddChapter && selectedChapter && (
                  <button
                    onClick={() => onGenerateChapter(selectedChapter.chapter_num)}
                    disabled={!directoryText || generatingChapterNum === selectedChapter.chapter_num}
                    className="px-3 py-1.5 text-xs bg-emerald-50 text-emerald-700 rounded-md border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
                  >
                    {generatingChapterNum === selectedChapter.chapter_num ? '生成中...' : 'AI 重新生成'}
                  </button>
                )}
                <button
                  onClick={handleSave}
                  className="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition-colors"
                >
                  保存
                </button>
                <button
                  onClick={handleCancel}
                  className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
                >
                  取消
                </button>
                {!showAddChapter && editingChapterId && (
                  <button
                    onClick={() => {
                      if (confirm('确定要删除这个章节吗？')) {
                        onDeleteChapter(editingChapterId)
                      }
                    }}
                    className="px-3 py-1.5 text-xs text-rose-400 hover:text-rose-600 transition-colors"
                  >
                    删除
                  </button>
                )}
              </div>
            </div>

            {/* Outline */}
            <div className="px-4 py-2 border-b border-slate-100">
              <label className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">大纲</label>
              <textarea
                value={chapterForm.outline || ''}
                onChange={(e) => {
                  setChapterForm({ ...chapterForm, outline: e.target.value })
                  setDirty(true)
                }}
                rows={2}
                placeholder="本章大纲..."
                className="mt-1 block w-full px-2 py-1.5 text-xs text-slate-600 bg-slate-50/50 border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
              />
            </div>

            {/* Draft - main editor */}
            <div className="flex-1 flex flex-col min-h-0 px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] font-medium text-slate-400 uppercase tracking-wider">正文</label>
                <span className="text-[10px] text-slate-400">
                  {wordCount.toLocaleString()} 字
                  {wordCount > 0 && ` / 约 ${(wordCount / 1000).toFixed(1)}k`}
                </span>
              </div>
              <textarea
                ref={draftRef}
                value={chapterForm.draft || ''}
                onChange={(e) => {
                  setChapterForm({ ...chapterForm, draft: e.target.value })
                  setDirty(true)
                }}
                placeholder={showAddChapter ? '在此输入章节正文...' : '在此编辑章节正文...'}
                className="flex-1 w-full px-3 py-2 text-sm text-slate-700 bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 resize-none leading-relaxed"
                style={{ minHeight: '300px' }}
              />
            </div>

            {/* Status bar */}
            <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-3">
                {showAddChapter ? (
                  <span className="text-xs text-indigo-600 font-medium">新建章节模式</span>
                ) : selectedChapter ? (
                  <>
                    <span className="text-xs text-slate-500">
                      第 {selectedChapter.chapter_num} 章
                    </span>
                    <span className="text-xs text-slate-300">|</span>
                    <span className="text-xs text-slate-500">
                      创建于 {new Date(selectedChapter.created_at).toLocaleDateString('zh-CN')}
                    </span>
                  </>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-400">快捷键: Ctrl+S 保存</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
