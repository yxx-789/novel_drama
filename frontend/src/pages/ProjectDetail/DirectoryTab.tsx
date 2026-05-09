import { ProgressBar, getTaskStepLabel } from './utils'

interface DirectoryTabProps {
  directoryText: string
  setDirectoryText: (v: string) => void
  directoryLoading: boolean
  directorySaving: boolean
  directoryGenerating: boolean
  activeTask: { id: string; type: string; progress: number; status: string } | null
  setDirty: (v: boolean) => void
  onSave: () => void
  onGenerate: () => void
  onExport: () => void
}

export default function DirectoryTab({
  directoryText,
  setDirectoryText,
  directoryLoading,
  directorySaving,
  directoryGenerating,
  activeTask,
  setDirty,
  onSave,
  onGenerate,
  onExport,
}: DirectoryTabProps) {
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-base font-serif font-medium text-slate-800">章节目录</h2>
        <div className="flex space-x-3">
          <button
            onClick={onExport}
            className="btn-secondary text-[10px] py-1.5 px-3"
          >
            导出 MD
          </button>
          <button
            onClick={onGenerate}
            disabled={directoryGenerating}
            className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {directoryGenerating ? '生成中...' : 'AI 生成目录'}
          </button>
          <button
            onClick={onSave}
            disabled={directorySaving}
            className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {directorySaving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
      {activeTask?.type === 'directory' && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}
      {directoryLoading ? (
        <p className="text-slate-400 text-xs">加载中...</p>
      ) : (
        <textarea
          value={directoryText}
          onChange={(e) => { setDirectoryText(e.target.value); setDirty(true) }}
          rows={24}
          className="block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm leading-relaxed"
          placeholder="在此编辑章节目录..."
        />
      )}
    </div>
  )
}
