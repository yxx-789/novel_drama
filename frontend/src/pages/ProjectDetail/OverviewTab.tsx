import { statusBadge } from './utils'
import type { Project } from '../../api/project'

interface OverviewTabProps {
  project: Project
  editing: boolean
  setEditing: (v: boolean) => void
  saving: boolean
  name: string
  setName: (v: string) => void
  topic: string
  setTopic: (v: string) => void
  genre: string
  setGenre: (v: string) => void
  numChapters: number
  setNumChapters: (v: number) => void
  wordNumber: number
  setWordNumber: (v: number) => void
  setDirty: (v: boolean) => void
  onSave: () => void
}

export default function OverviewTab({
  project,
  editing,
  setEditing,
  saving,
  name,
  setName,
  topic,
  setTopic,
  genre,
  setGenre,
  numChapters,
  setNumChapters,
  wordNumber,
  setWordNumber,
  setDirty,
  onSave,
}: OverviewTabProps) {
  return (
    <div className="glass-panel p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-base font-serif font-medium text-slate-800">项目信息</h2>
        {!editing && (
          <button
            onClick={() => { setEditing(true); setDirty(true) }}
            className="px-4 py-2 text-sm font-medium text-indigo-600 hover:text-indigo-500"
          >
            编辑
          </button>
        )}
      </div>

      {editing ? (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">项目名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">主题</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">类型</label>
            <select
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">请选择类型</option>
              <option value="玄幻">玄幻</option>
              <option value="都市">都市</option>
              <option value="科幻">科幻</option>
              <option value="仙侠">仙侠</option>
              <option value="历史">历史</option>
              <option value="悬疑">悬疑</option>
              <option value="言情">言情</option>
              <option value="其他">其他</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">计划章节数</label>
              <input
                type="number"
                value={numChapters}
                onChange={(e) => setNumChapters(Number(e.target.value))}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                min={1}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">每章字数</label>
              <input
                type="number"
                value={wordNumber}
                onChange={(e) => setWordNumber(Number(e.target.value))}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                min={500}
                step={500}
              />
            </div>
          </div>
          <div className="flex justify-end space-x-4 pt-4">
            <button
              onClick={() => { setEditing(false); setDirty(false) }}
              className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50"
            >
              取消
            </button>
            <button
              onClick={onSave}
              disabled={saving}
              className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
            >
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-400">主题</p>
              <p className="text-base font-medium text-gray-900">{project.topic || '未设置'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">类型</p>
              <p className="text-base font-medium text-gray-900">{project.genre || '未设置'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">计划章节数</p>
              <p className="text-base font-medium text-gray-900">{project.num_chapters} 章</p>
            </div>
            <div>
              <p className="text-xs text-slate-400">每章字数</p>
              <p className="text-base font-medium text-gray-900">{project.word_number} 字</p>
            </div>
          </div>
          <div>
            <p className="text-xs text-slate-400">状态</p>
            {statusBadge(project.status)}
          </div>
        </div>
      )}
    </div>
  )
}
