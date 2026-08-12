import { statusBadge } from './utils'
import type { Project } from '../../api/project'
import { DIMENSION_OPTIONS } from '../../constants/blocks'

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
  storyShape: string
  setStoryShape: (v: string) => void
  totalChaptersTarget: number | null
  setTotalChaptersTarget: (v: number | null) => void
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
  storyShape,
  setStoryShape,
  totalChaptersTarget,
  setTotalChaptersTarget,
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
              {DIMENSION_OPTIONS.core_genre.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
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
          <div>
            <label className="block text-sm font-medium text-gray-700">故事形态</label>
            <div className="mt-1 space-y-2">
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input
                  type="radio"
                  name="storyShapeEdit"
                  checked={storyShape === 'final'}
                  onChange={() => { setStoryShape('final'); setTotalChaptersTarget(null) }}
                  className="accent-indigo-600"
                />
                <span>短篇完结（第 {numChapters} 章即全书结局）</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                <input
                  type="radio"
                  name="storyShapeEdit"
                  checked={storyShape === 'open'}
                  onChange={() => setStoryShape('open')}
                  className="accent-indigo-600"
                />
                <span>连载开篇（第 {numChapters} 章留钩子，后续可续写）</span>
              </label>
            </div>
            {storyShape === 'open' && (
              <div className="mt-2">
                {totalChaptersTarget ? (
                  <p className="text-sm text-gray-700">
                    全书目标总章数：<span className="font-medium">{totalChaptersTarget}</span> 章
                    <span className="ml-2 text-xs text-gray-400">（创建后不可修改）</span>
                  </p>
                ) : (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">全书目标总章数 M</label>
                    <input
                      type="number"
                      min={10}
                      max={1000}
                      value={totalChaptersTarget ?? ''}
                      onChange={(e) => setTotalChaptersTarget(e.target.value === '' ? null : Number(e.target.value))}
                      placeholder="10~1000"
                      className="mt-1 w-full rounded-lg border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                    />
                    <p className="mt-1 text-xs text-amber-600">该数字创建后不可修改，请谨慎填写</p>
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex justify-end space-x-4 pt-4">
            <button
              onClick={() => {
                setEditing(false)
                setDirty(false)
                setName(project.name)
                setTopic(project.topic || '')
                setGenre(project.genre || '')
                setNumChapters(project.num_chapters)
                setWordNumber(project.word_number)
              }}
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
              <p className="text-xs text-slate-400">故事形态</p>
              <p className="text-base font-medium text-gray-900">
                {project.story_shape === 'open' ? '连载开篇' : '短篇完结'}
              </p>
              {project.story_shape === 'open' && project.total_chapters_target && (
                <p className="text-base font-medium text-gray-900">全书目标：{project.total_chapters_target} 章（锁定）</p>
              )}
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
