import { ProgressBar, getTaskStepLabel } from './utils'

interface ArchitectureTabProps {
  architectureText: string
  setArchitectureText: (v: string) => void
  characterText: string
  architectureLoading: boolean
  architectureSaving: boolean
  architectureGenerating: boolean
  activeTask: { id: string; type: string; progress: number; status: string } | null
  setDirty: (v: boolean) => void
  onSave: () => void
  onGenerate: () => void
  onExport: () => void
}

export default function ArchitectureTab({
  architectureText,
  setArchitectureText,
  characterText,
  architectureLoading,
  architectureSaving,
  architectureGenerating,
  activeTask,
  setDirty,
  onSave,
  onGenerate,
  onExport,
}: ArchitectureTabProps) {
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-base font-serif font-medium text-slate-800">小说架构</h2>
        <div className="flex space-x-3">
          <button
            onClick={onExport}
            className="btn-secondary text-[10px] py-1.5 px-3"
          >
            导出 MD
          </button>
          <button
            onClick={onGenerate}
            disabled={architectureGenerating}
            className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {architectureGenerating ? '生成中...' : 'AI 生成架构'}
          </button>
          <button
            onClick={onSave}
            disabled={architectureSaving}
            className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {architectureSaving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
      {activeTask?.type === 'architecture' && (
        <ProgressBar
          progress={activeTask.progress}
          label={getTaskStepLabel(activeTask.type, activeTask.progress)}
        />
      )}
      {architectureLoading ? (
        <p className="text-slate-400 text-xs">加载中...</p>
      ) : (
        <>
          <textarea
            value={architectureText}
            onChange={(e) => { setArchitectureText(e.target.value); setDirty(true) }}
            rows={20}
            className="block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm leading-relaxed"
            placeholder="在此编辑小说架构：世界观、主线情节、角色设定..."
          />
          <div className="mt-4">
            <h3 className="text-base font-semibold text-gray-800 mb-2">人物状态</h3>
            {characterText ? (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                {characterText}
              </div>
            ) : (
              <p className="text-xs text-slate-400">尚未生成人物状态，点击「AI 生成架构」后会自动生成。</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
