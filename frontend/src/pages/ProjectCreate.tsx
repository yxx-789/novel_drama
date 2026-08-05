import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { createProject } from '../api/project'
import { importInspiration } from '../api/inspiration'
import { queryClient } from '../queryClient'

function ProjectCreate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryTopic = searchParams.get('topic') || ''
  const inspiration = {
    note_id: searchParams.get('note_id') || '',
    title: queryTopic,
    summary: searchParams.get('summary') || '',
    likes: Number(searchParams.get('likes') || 0),
    collects: 0,
    url: searchParams.get('url') || '',
    author: searchParams.get('author') || '',
    fetched_at: new Date().toISOString(),
  }
  const [name, setName] = useState(queryTopic)
  const [topic, setTopic] = useState(queryTopic)
  const [genre, setGenre] = useState('')
  const [numChapters, setNumChapters] = useState(20)
  const [wordNumber, setWordNumber] = useState(3000)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: async (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      if (inspiration.note_id) {
        try {
          await importInspiration(data.id, { ...inspiration, title: topic || queryTopic })
        } catch (e) {
          console.error('导入灵感失败', e)
        }
      }
      navigate(`/projects/${data.id}`)
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || '创建项目失败')
    },
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    mutation.mutate({
      name,
      topic: topic || undefined,
      genre: genre || undefined,
      num_chapters: numChapters,
      word_number: wordNumber,
    })
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold text-gray-900">创建项目</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        <div className="bg-white shadow rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                项目名称 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="请输入项目名称"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                主题
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="小说主题，如：修真世界、未来都市"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                类型
              </label>
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
                <label className="block text-sm font-medium text-gray-700">
                  计划章节数
                </label>
                <input
                  type="number"
                  value={numChapters}
                  onChange={(e) => setNumChapters(Number(e.target.value))}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  min={1}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  每章字数
                </label>
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

            <div className="flex justify-end space-x-4">
              <button
                type="button"
                onClick={() => navigate('/projects')}
                className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={mutation.isPending}
                className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {mutation.isPending ? '创建中...' : '创建项目'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}

export default ProjectCreate
