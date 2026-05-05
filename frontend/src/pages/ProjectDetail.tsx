import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getProject, updateProject } from '../api/project'
import type { Project } from '../api/project'
import { listChapters, createChapter, updateChapter, deleteChapter } from '../api/chapter'
import type { Chapter, CreateChapterRequest } from '../api/chapter'
import { getAsset, upsertAsset } from '../api/asset'
import { createTask, getTask } from '../api/task'
import { listDramaEpisodes } from '../api/drama'
import type { DramaEpisode } from '../api/drama'

type TabKey = 'overview' | 'architecture' | 'directory' | 'chapters' | 'drama'

function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<TabKey>('overview')

  // Overview edit state
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [topic, setTopic] = useState('')
  const [genre, setGenre] = useState('')
  const [numChapters, setNumChapters] = useState(0)
  const [wordNumber, setWordNumber] = useState(0)

  // Architecture tab state
  const [architectureText, setArchitectureText] = useState('')
  const [architectureLoading, setArchitectureLoading] = useState(false)
  const [architectureSaving, setArchitectureSaving] = useState(false)
  const [architectureGenerating, setArchitectureGenerating] = useState(false)

  // Directory tab state
  const [directoryText, setDirectoryText] = useState('')
  const [directoryLoading, setDirectoryLoading] = useState(false)
  const [directorySaving, setDirectorySaving] = useState(false)
  const [directoryGenerating, setDirectoryGenerating] = useState(false)

  // Chapters tab state
  const [showAddChapter, setShowAddChapter] = useState(false)
  const [editingChapterId, setEditingChapterId] = useState<string | null>(null)
  const [generatingChapterNum, setGeneratingChapterNum] = useState<number | null>(null)
  const [chapterForm, setChapterForm] = useState<CreateChapterRequest>({
    chapter_num: 1,
    title: '',
    outline: '',
    draft: '',
    finalized_text: '',
    status: 'draft',
  })

  // Drama tab state
  const [dramaEpisodes, setDramaEpisodes] = useState<DramaEpisode[]>([])
  const [dramaLoading, setDramaLoading] = useState(false)
  const [dramaPlanGenerating, setDramaPlanGenerating] = useState(false)
  const [generatingDramaEpisodeNum, setGeneratingDramaEpisodeNum] = useState<number | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      if (!id) return
      try {
        const [projectData, chaptersData] = await Promise.all([
          getProject(id),
          listChapters(id),
        ])
        setProject(projectData)
        setName(projectData.name)
        setTopic(projectData.topic || '')
        setGenre(projectData.genre || '')
        setNumChapters(projectData.num_chapters)
        setWordNumber(projectData.word_number)
        setChapters(chaptersData)
      } catch (err: any) {
        setError(err.response?.data?.detail || '获取数据失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  // Load architecture asset when tab switches
  useEffect(() => {
    if (activeTab !== 'architecture' || !id) return
    const load = async () => {
      setArchitectureLoading(true)
      try {
        const asset = await getAsset(id, 'architecture')
        setArchitectureText(asset.content_text || '')
      } catch (err: any) {
        if (err.response?.status === 404) {
          setArchitectureText('')
        } else {
          setError(err.response?.data?.detail || '获取架构失败')
        }
      } finally {
        setArchitectureLoading(false)
      }
    }
    load()
  }, [activeTab, id])

  // Load directory asset when tab switches
  useEffect(() => {
    if (activeTab !== 'directory' || !id) return
    const load = async () => {
      setDirectoryLoading(true)
      try {
        const asset = await getAsset(id, 'directory')
        setDirectoryText(asset.content_text || '')
      } catch (err: any) {
        if (err.response?.status === 404) {
          setDirectoryText('')
        } else {
          setError(err.response?.data?.detail || '获取目录失败')
        }
      } finally {
        setDirectoryLoading(false)
      }
    }
    load()
  }, [activeTab, id])

  // Load drama episodes when tab switches
  useEffect(() => {
    if (activeTab !== 'drama' || !id) return
    const load = async () => {
      setDramaLoading(true)
      try {
        const episodes = await listDramaEpisodes(id)
        setDramaEpisodes(episodes)
      } catch (err: any) {
        setError(err.response?.data?.detail || '获取短剧列表失败')
      } finally {
        setDramaLoading(false)
      }
    }
    load()
  }, [activeTab, id])

  const handleSaveProject = async () => {
    if (!id) return
    setSaving(true)
    try {
      const updated = await updateProject(id, {
        name,
        topic: topic || undefined,
        genre: genre || undefined,
        num_chapters: numChapters,
        word_number: wordNumber,
      })
      setProject(updated)
      setEditing(false)
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleSaveArchitecture = async () => {
    if (!id) return
    setArchitectureSaving(true)
    try {
      await upsertAsset(id, 'architecture', { content_text: architectureText })
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存架构失败')
    } finally {
      setArchitectureSaving(false)
    }
  }

  const handleGenerateArchitecture = async () => {
    if (!id) return
    setArchitectureGenerating(true)
    try {
      const task = await createTask(id, { task_type: 'architecture' })
      setError('')
      pollTask(
        task.id,
        async () => {
          const asset = await getAsset(id, 'architecture')
          setArchitectureText(asset.content_text || '')
          setArchitectureGenerating(false)
        },
        (msg) => {
          setError(`架构生成失败: ${msg}`)
          setArchitectureGenerating(false)
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setArchitectureGenerating(false)
    }
  }

  const handleSaveDirectory = async () => {
    if (!id) return
    setDirectorySaving(true)
    try {
      await upsertAsset(id, 'directory', { content_text: directoryText })
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存目录失败')
    } finally {
      setDirectorySaving(false)
    }
  }

  const handleGenerateDirectory = async () => {
    if (!id) return
    setDirectoryGenerating(true)
    try {
      const task = await createTask(id, { task_type: 'directory' })
      setError('')
      pollTask(
        task.id,
        async () => {
          const [asset, chaptersData] = await Promise.all([
            getAsset(id, 'directory'),
            listChapters(id),
          ])
          setDirectoryText(asset.content_text || '')
          setChapters(chaptersData)
          setDirectoryGenerating(false)
        },
        (msg) => {
          setError(`目录生成失败: ${msg}`)
          setDirectoryGenerating(false)
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setDirectoryGenerating(false)
    }
  }

  const handleGenerateChapter = async (chapterNum: number) => {
    if (!id) return
    setGeneratingChapterNum(chapterNum)
    try {
      const task = await createTask(id, { task_type: 'chapter', params: { chapter_num: chapterNum } })
      setError('')
      pollTask(
        task.id,
        async () => {
          const chaptersData = await listChapters(id)
          setChapters(chaptersData)
          setGeneratingChapterNum(null)
        },
        (msg) => {
          setError(`第${chapterNum}章生成失败: ${msg}`)
          setGeneratingChapterNum(null)
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setGeneratingChapterNum(null)
    }
  }

  const handleGenerateDramaPlan = async () => {
    if (!id) return
    setDramaPlanGenerating(true)
    try {
      const task = await createTask(id, { task_type: 'drama_plan' })
      setError('')
      pollTask(
        task.id,
        async () => {
          const episodes = await listDramaEpisodes(id)
          setDramaEpisodes(episodes)
          setDramaPlanGenerating(false)
        },
        (msg) => {
          setError(`短剧计划生成失败: ${msg}`)
          setDramaPlanGenerating(false)
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setDramaPlanGenerating(false)
    }
  }

  const handleGenerateDramaEpisode = async (episodeNum: number) => {
    if (!id) return
    setGeneratingDramaEpisodeNum(episodeNum)
    try {
      const task = await createTask(id, { task_type: 'drama_episode', params: { episode_num: episodeNum } })
      setError('')
      pollTask(
        task.id,
        async () => {
          const episodes = await listDramaEpisodes(id)
          setDramaEpisodes(episodes)
          setGeneratingDramaEpisodeNum(null)
        },
        (msg) => {
          setError(`第${episodeNum}集生成失败: ${msg}`)
          setGeneratingDramaEpisodeNum(null)
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setGeneratingDramaEpisodeNum(null)
    }
  }

  // Chapter handlers
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

  const handleAddChapter = async () => {
    if (!id) return
    try {
      const newChapter = await createChapter(id, chapterForm)
      setChapters([...chapters, newChapter])
      setShowAddChapter(false)
      resetChapterForm()
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建章节失败')
    }
  }

  const handleUpdateChapter = async (chapterId: string) => {
    try {
      const updated = await updateChapter(chapterId, chapterForm)
      setChapters(chapters.map((c) => (c.id === chapterId ? updated : c)))
      setEditingChapterId(null)
      resetChapterForm()
    } catch (err: any) {
      setError(err.response?.data?.detail || '更新章节失败')
    }
  }

  const handleDeleteChapter = async (chapterId: string) => {
    if (!window.confirm('确定要删除这个章节吗？')) return
    try {
      await deleteChapter(chapterId)
      setChapters(chapters.filter((c) => c.id !== chapterId))
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除章节失败')
    }
  }

  const startEditChapter = (chapter: Chapter) => {
    setEditingChapterId(chapter.id)
    setChapterForm({
      chapter_num: chapter.chapter_num,
      title: chapter.title,
      outline: chapter.outline || '',
      draft: chapter.draft || '',
      finalized_text: chapter.finalized_text || '',
      status: chapter.status,
    })
  }

  const pollTask = async (taskId: string, onSuccess: () => void, onError?: (msg: string) => void) => {
    const interval = setInterval(async () => {
      try {
        const task = await getTask(taskId)
        if (task.status === 'success') {
          clearInterval(interval)
          onSuccess()
        } else if (task.status === 'failed') {
          clearInterval(interval)
          onError?.(task.error_msg || '任务失败')
        }
      } catch {
        // ignore polling errors
      }
    }, 3000)
  }

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-600',
      draft_generated: 'bg-blue-100 text-blue-700',
      generating: 'bg-yellow-100 text-yellow-700',
      finalized: 'bg-green-100 text-green-700',
    }
    const label: Record<string, string> = {
      draft: '草稿',
      draft_generated: '已生成',
      generating: '生成中',
      finalized: '已终稿',
    }
    return (
      <span className={`inline-block text-xs px-2 py-1 rounded-full ${map[status] || map.draft}`}>
        {label[status] || status}
      </span>
    )
  }

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'overview', label: '概览' },
    { key: 'architecture', label: '架构' },
    { key: 'directory', label: '目录' },
    { key: 'chapters', label: '章节' },
    { key: 'drama', label: '短剧改编' },
  ]

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">加载中...</p>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">{error || '项目不存在'}</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/projects')}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              ← 返回列表
            </button>
            <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          </div>
        </div>
      </header>

      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="-mb-px flex space-x-8" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => {
                  setActiveTab(tab.key)
                  setError('')
                }}
                className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.key
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-900">项目信息</h2>
              {!editing && (
                <button
                  onClick={() => setEditing(true)}
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
                    onClick={() => setEditing(false)}
                    className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSaveProject}
                    disabled={saving}
                    className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {saving ? '保存中...' : '保存'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">主题</p>
                    <p className="text-base font-medium text-gray-900">{project.topic || '未设置'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">类型</p>
                    <p className="text-base font-medium text-gray-900">{project.genre || '未设置'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">计划章节数</p>
                    <p className="text-base font-medium text-gray-900">{project.num_chapters} 章</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">每章字数</p>
                    <p className="text-base font-medium text-gray-900">{project.word_number} 字</p>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-gray-500">状态</p>
                  {statusBadge(project.status)}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'architecture' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">小说架构</h2>
              <div className="flex space-x-3">
                <button
                  onClick={handleGenerateArchitecture}
                  disabled={architectureGenerating}
                  className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {architectureGenerating ? '生成中...' : 'AI 生成架构'}
                </button>
                <button
                  onClick={handleSaveArchitecture}
                  disabled={architectureSaving}
                  className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {architectureSaving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
            {architectureLoading ? (
              <p className="text-gray-500 text-sm">加载中...</p>
            ) : (
              <textarea
                value={architectureText}
                onChange={(e) => setArchitectureText(e.target.value)}
                rows={24}
                className="block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm leading-relaxed"
                placeholder="在此编辑小说架构：世界观、主线情节、角色设定..."
              />
            )}
          </div>
        )}

        {activeTab === 'directory' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-gray-900">章节目录</h2>
              <div className="flex space-x-3">
                <button
                  onClick={handleGenerateDirectory}
                  disabled={directoryGenerating}
                  className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
                >
                  {directoryGenerating ? '生成中...' : 'AI 生成目录'}
                </button>
                <button
                  onClick={handleSaveDirectory}
                  disabled={directorySaving}
                  className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {directorySaving ? '保存中...' : '保存'}
                </button>
              </div>
            </div>
            {directoryLoading ? (
              <p className="text-gray-500 text-sm">加载中...</p>
            ) : (
              <textarea
                value={directoryText}
                onChange={(e) => setDirectoryText(e.target.value)}
                rows={24}
                className="block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm leading-relaxed"
                placeholder="在此编辑章节目录..."
              />
            )}
          </div>
        )}

        {activeTab === 'chapters' && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-900">章节列表</h2>
              <button
                onClick={() => {
                  resetChapterForm()
                  setShowAddChapter(true)
                  setEditingChapterId(null)
                }}
                className="px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700"
              >
                + 新建章节
              </button>
            </div>

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
                      resetChapterForm()
                    }}
                    className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 hover:bg-gray-50"
                  >
                    取消
                  </button>
                  <button
                    onClick={() =>
                      editingChapterId ? handleUpdateChapter(editingChapterId) : handleAddChapter()
                    }
                    className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700"
                  >
                    {editingChapterId ? '保存' : '创建'}
                  </button>
                </div>
              </div>
            )}

            {chapters.length === 0 ? (
              <p className="text-gray-500 text-sm">暂无章节，点击上方按钮创建</p>
            ) : (
              <div className="space-y-3">
                {chapters
                  .sort((a, b) => a.chapter_num - b.chapter_num)
                  .map((chapter) => (
                    <div
                      key={chapter.id}
                      className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex justify-between items-start">
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
                        <div className="flex items-center space-x-2 ml-4">
                          <button
                            onClick={() => handleGenerateChapter(chapter.chapter_num)}
                            disabled={generatingChapterNum === chapter.chapter_num}
                            className="text-sm text-emerald-600 hover:text-emerald-500 disabled:opacity-50"
                          >
                            {generatingChapterNum === chapter.chapter_num ? '生成中...' : 'AI 生成'}
                          </button>
                          <button
                            onClick={() => startEditChapter(chapter)}
                            className="text-sm text-indigo-600 hover:text-indigo-500"
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => handleDeleteChapter(chapter.id)}
                            className="text-sm text-red-600 hover:text-red-500"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'drama' && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-gray-900">短剧改编</h2>
              <button
                onClick={handleGenerateDramaPlan}
                disabled={dramaPlanGenerating}
                className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {dramaPlanGenerating ? '生成中...' : 'AI 生成改编计划'}
              </button>
            </div>

            {dramaLoading ? (
              <p className="text-gray-500 text-sm">加载中...</p>
            ) : dramaEpisodes.length === 0 ? (
              <p className="text-gray-500 text-sm">暂无短剧集，点击上方按钮生成改编计划</p>
            ) : (
              <div className="space-y-3">
                {dramaEpisodes.map((episode) => (
                  <div
                    key={episode.id}
                    className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <span className="text-sm font-medium text-gray-500">
                            第{episode.episode_num}集
                          </span>
                          <h3 className="text-base font-semibold text-gray-900">
                            {episode.title}
                          </h3>
                          {statusBadge(episode.status)}
                        </div>
                        {episode.source_chapters && (
                          <p className="mt-2 text-sm text-gray-600">
                            来源：{episode.source_chapters}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2 ml-4">
                        <button
                          onClick={() => handleGenerateDramaEpisode(episode.episode_num)}
                          disabled={generatingDramaEpisodeNum === episode.episode_num}
                          className="text-sm text-emerald-600 hover:text-emerald-500 disabled:opacity-50"
                        >
                          {generatingDramaEpisodeNum === episode.episode_num ? '生成中...' : '生成脚本'}
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default ProjectDetail
