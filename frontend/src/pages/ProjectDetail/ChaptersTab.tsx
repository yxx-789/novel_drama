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
  const resetChapterForm = () => {
    setChapterForm({
      chapter_num: chapters.length + 1,
      title: '',
      outline: '',
      draft: '',
      finalized_text: '',
      status: 'draft',
    })
  }

  const startEditChapter = (chapter: Chapter) => {
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
  }

  return (
    <div className="glass-panel p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-base font-serif font-medium text-slate-800">章节列表</h2>
        <div className="flex items-center space-x-2">
          <div className="relative">
            <svg className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            <input
              type="text"
              placeholder="搜索章节..."
              value={chapterSearchQuery}
              onChange={(e) => setChapterSearchQuery(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 w-48"
            />
          </div>
          <button
            onClick={onExport}
            className="btn-secondary text-[10px] py-1.5 px-3"
          >
            导出 MD
          </button>
          <button
            onClick={onGenerateBatch}
            disabled={!directoryText || batchGenerating}
            title={!directoryText ? '请先生成章节目录' : ''}
            className="px-3 py-1.5 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
          >
            {batchGenerating ? '批量生成中...' : 'AI 批量生成全部'}
          </button>
          <button
            onClick={() => {
              resetChapterForm()
              setShowAddChapter(true)
              setDirty(true)
              setEditingChapterId(null)
            }}
            className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700"
          >
            + 新建章节
          </button>
        </div>
      </div>
      {(activeTask?.type === 'chapter' || activeTask?.type === 'batch_chapters') && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}

      {!directoryText && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
          尚未生成章节目录，请先切换到「目录」Tab 点击「AI 生成目录」后再生成章节正文。
        </div>
      )}

      {(showAddChapter || editingChapterId) && (
        <div className="mb-6 p-4 bg-gray-50 rounded-lg space-y-3">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">章节序号</label>
              <input
                type="number"
                value={chapterForm.chapter_num}
                onChange={(e) =>
                  setChapterForm({ ...chapterForm, chapter_num: Number(e.target.value) })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                min={1}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">状态</label>
              <select
                value={chapterForm.status}
                onChange={(e) =>
                  setChapterForm({ ...chapterForm, status: e.target.value as any })
                }
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="draft">草稿</option>
                <option value="draft_generated">已生成</option>
                <option value="generating">生成中</option>
                <option value="finalized">已终稿</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">标题</label>
            <input
              type="text"
              value={chapterForm.title || ''}
              onChange={(e) => setChapterForm({ ...chapterForm, title: e.target.value })}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">大纲</label>
            <textarea
              value={chapterForm.outline || ''}
              onChange={(e) => setChapterForm({ ...chapterForm, outline: e.target.value })}
              rows={3}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">草稿</label>
            <textarea
              value={chapterForm.draft || ''}
              onChange={(e) => setChapterForm({ ...chapterForm, draft: e.target.value })}
              rows={4}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div className="flex justify-end space-x-3">
            <button
              onClick={() => {
                setShowAddChapter(false)
                setEditingChapterId(null)
                setDirty(false)
                resetChapterForm()
              }}
              className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50"
            >
              取消
            </button>
            <button
              onClick={() =>
                editingChapterId ? onUpdateChapter(editingChapterId) : onAddChapter()
              }
              className="btn-primary"
            >
              {editingChapterId ? '保存' : '创建'}
            </button>
          </div>
        </div>
      )}

      {chapters.length === 0 ? (
        <p className="text-slate-400 text-xs">暂无章节，点击上方按钮创建</p>
      ) : (
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedChapterIds.size === chapters.length && chapters.length > 0}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedChapterIds(new Set(chapters.map((c) => c.id)))
                  } else {
                    setSelectedChapterIds(new Set())
                  }
                }}
                className="rounded border-slate-300 text-slate-600 focus:ring-slate-200"
              />
              <span className="text-xs text-slate-500">全选</span>
            </label>
            {selectedChapterIds.size > 0 && (
              <button
                onClick={() => onExportBatch(Array.from(selectedChapterIds))}
                className="btn-secondary text-[10px] py-1.5 px-3"
              >
                导出选中 ({selectedChapterIds.size})
              </button>
            )}
          </div>
          <div className="space-y-3">
            {chapters
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
              .map((chapter) => (
                <div
                  key={chapter.id}
                  className="glass-panel p-4 card-hover"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex items-start space-x-3 flex-1">
                      <input
                        type="checkbox"
                        checked={selectedChapterIds.has(chapter.id)}
                        onChange={(e) => {
                          const next = new Set(selectedChapterIds)
                          if (e.target.checked) {
                            next.add(chapter.id)
                          } else {
                            next.delete(chapter.id)
                          }
                          setSelectedChapterIds(next)
                        }}
                        className="mt-1 rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                      />
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <span className="text-sm font-medium text-gray-500">
                            第{chapter.chapter_num}章
                          </span>
                          <h3 className="text-base font-semibold text-gray-900">
                            {chapter.title}
                          </h3>
                          {statusBadge(chapter.status)}
                        </div>
                        {chapter.outline && (
                          <p className="mt-2 text-sm text-gray-600 line-clamp-2">
                            {chapter.outline}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 ml-4">
                      <button
                        onClick={() => onGenerateChapter(chapter.chapter_num)}
                        disabled={!directoryText || generatingChapterNum === chapter.chapter_num}
                        title={!directoryText ? '请先生成章节目录' : ''}
                        className="text-[10px] font-bold tracking-widest text-emerald-600 hover:text-emerald-700 disabled:opacity-50 transition-colors uppercase"
                      >
                        {generatingChapterNum === chapter.chapter_num ? '生成中...' : 'AI 生成'}
                      </button>
                      <button
                        onClick={() => startEditChapter(chapter)}
                        className="text-[10px] font-bold tracking-widest text-slate-400 hover:text-slate-700 transition-colors uppercase"
                      >
                        编辑
                      </button>
                      <button
                        onClick={() => onDeleteChapter(chapter.id)}
                        className="btn-ghost text-rose-400 hover:text-rose-500"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
