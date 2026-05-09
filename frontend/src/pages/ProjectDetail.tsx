import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getProject, updateProject } from '../api/project'
import type { Project } from '../api/project'
import { listChapters, createChapter, updateChapter, deleteChapter, exportChaptersBatch } from '../api/chapter'
import type { Chapter, CreateChapterRequest } from '../api/chapter'
import { getAsset, upsertAsset, exportAsset } from '../api/asset'
import { exportChapters } from '../api/chapter'
import { getTask, listTasks } from '../api/task'
import {
  generateArchitecture,
  generateDirectory,
  generateChapter,
  generateDramaPlan,
  generateDramaEpisode,
  generateBatchChapters,
  generateDramaBatch,
} from '../api/generate'
import { listDramaEpisodes, exportEpisodeScript, exportEpisodesBatch } from '../api/drama'
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
  const [characterText, setCharacterText] = useState('')
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
  const [batchGenerating, setBatchGenerating] = useState(false)
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
  const [batchDramaGenerating, setBatchDramaGenerating] = useState(false)
  const [generatingDramaEpisodeNum, setGeneratingDramaEpisodeNum] = useState<number | null>(null)
  const [expandedDramaEpisodeId, setExpandedDramaEpisodeId] = useState<string | null>(null)

  // Export selection state
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(new Set())
  const [selectedEpisodeIds, setSelectedEpisodeIds] = useState<Set<string>>(new Set())

  // Chapter selector modal state
  const [showChapterSelector, setShowChapterSelector] = useState(false)
  const [chapterSelectorTarget, setChapterSelectorTarget] = useState<{ episodeNum: number; defaults: number[] } | null>(null)
  const [chapterSelectorSelected, setChapterSelectorSelected] = useState<Set<number>>(new Set())

  // Active task progress tracking
  const [activeTask, setActiveTask] = useState<{ id: string; type: string; progress: number; status: string } | null>(null)

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

        // 恢复进行中的任务（只恢复30分钟内创建的，避免显示死任务）
        try {
          const tasks = await listTasks(id)
          const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000).toISOString()
          const runningTask = tasks.find(
            (t) =>
              (t.status === 'pending' || t.status === 'running') &&
              t.created_at >= thirtyMinutesAgo
          )
          if (runningTask) {
            setActiveTask({
              id: runningTask.id,
              type: runningTask.task_type,
              progress: runningTask.progress,
              status: runningTask.status,
            })
            // 根据任务类型设置 loading 状态
            if (runningTask.task_type === 'architecture') {
              setArchitectureGenerating(true)
            } else if (runningTask.task_type === 'directory') {
              setDirectoryGenerating(true)
            } else if (runningTask.task_type === 'chapter') {
              const chNum = runningTask.params?.chapter_num
              if (typeof chNum === 'number') {
                setGeneratingChapterNum(chNum)
              }
            } else if (runningTask.task_type === 'batch_chapters') {
              setBatchGenerating(true)
            } else if (runningTask.task_type === 'drama_plan') {
              setDramaPlanGenerating(true)
            } else if (runningTask.task_type === 'drama_episode') {
              const epNum = runningTask.params?.episode_num
              if (typeof epNum === 'number') {
                setGeneratingDramaEpisodeNum(epNum)
              }
            }
            // 继续轮询
            pollTask(
              runningTask.id,
              async () => {
                setActiveTask(null)
                setArchitectureGenerating(false)
                setDirectoryGenerating(false)
                setGeneratingChapterNum(null)
                setBatchGenerating(false)
                setDramaPlanGenerating(false)
                setGeneratingDramaEpisodeNum(null)
                // 刷新对应数据
                if (runningTask.task_type === 'architecture' && id) {
                  const asset = await getAsset(id, 'architecture')
                  setArchitectureText(asset.content_text || '')
                } else if (runningTask.task_type === 'directory' && id) {
                  const asset = await getAsset(id, 'directory')
                  setDirectoryText(asset.content_text || '')
                  const updatedChapters = await listChapters(id)
                  setChapters(updatedChapters)
                } else if ((runningTask.task_type === 'chapter' || runningTask.task_type === 'batch_chapters') && id) {
                  const updatedChapters = await listChapters(id)
                  setChapters(updatedChapters)
                } else if (runningTask.task_type.startsWith('drama') && id) {
                  const episodes = await listDramaEpisodes(id)
                  setDramaEpisodes(episodes)
                }
              },
              (msg) => {
                setError(`任务恢复后失败: ${msg}`)
                setActiveTask(null)
                setArchitectureGenerating(false)
                setDirectoryGenerating(false)
                setGeneratingChapterNum(null)
                setBatchGenerating(false)
                setDramaPlanGenerating(false)
                setGeneratingDramaEpisodeNum(null)
              },
              (progress, status) => {
                setActiveTask((prev) =>
                  prev ? { ...prev, progress, status } : null
                )
              }
            )
          }
        } catch {
          // ignore task list errors
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || '获取数据失败')
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [id])

  // Load architecture + characters assets when tab switches
  useEffect(() => {
    if (activeTab !== 'architecture' || !id) return
    const load = async () => {
      setArchitectureLoading(true)
      try {
        const [archAsset, charAsset] = await Promise.all([
          getAsset(id, 'architecture').catch((e: any) => {
            if (e.response?.status === 404) return { content_text: '' }
            throw e
          }),
          getAsset(id, 'characters').catch((e: any) => {
            if (e.response?.status === 404) return { content_text: '' }
            throw e
          }),
        ])
        setArchitectureText(archAsset.content_text || '')
        setCharacterText(charAsset.content_text || '')
      } catch (err: any) {
        setError(err.response?.data?.detail || '获取架构/人物状态失败')
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

  // Load directory asset when chapters tab switches (needed for generation check)
  useEffect(() => {
    if (activeTab !== 'chapters' || !id) return
    const load = async () => {
      try {
        const asset = await getAsset(id, 'directory')
        setDirectoryText(asset.content_text || '')
      } catch (err: any) {
        if (err.response?.status === 404) {
          setDirectoryText('')
        }
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
      const task = await generateArchitecture(id)
      setError('')
      setActiveTask({ id: task.id, type: 'architecture', progress: 0, status: 'pending' })
      pollTask(
        task.id,
        async () => {
          const asset = await getAsset(id, 'architecture')
          setArchitectureText(asset.content_text || '')
          setArchitectureGenerating(false)
          setActiveTask(null)
        },
        (msg) => {
          setError(`架构生成失败: ${msg}`)
          setArchitectureGenerating(false)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setArchitectureGenerating(false)
      setActiveTask(null)
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
      const task = await generateDirectory(id)
      setError('')
      setActiveTask({ id: task.id, type: 'directory', progress: 0, status: 'pending' })
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
          setActiveTask(null)
        },
        (msg) => {
          setError(`目录生成失败: ${msg}`)
          setDirectoryGenerating(false)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setDirectoryGenerating(false)
      setActiveTask(null)
    }
  }

  const handleGenerateChapter = async (chapterNum: number) => {
    if (!id) return
    setGeneratingChapterNum(chapterNum)
    try {
      const task = await generateChapter(id, chapterNum)
      setError('')
      setActiveTask({ id: task.id, type: 'chapter', progress: 0, status: 'pending' })
      pollTask(
        task.id,
        async () => {
          const chaptersData = await listChapters(id)
          setChapters(chaptersData)
          setGeneratingChapterNum(null)
          setActiveTask(null)
        },
        (msg) => {
          setError(`第${chapterNum}章生成失败: ${msg}`)
          setGeneratingChapterNum(null)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setGeneratingChapterNum(null)
      setActiveTask(null)
    }
  }

  const handleGenerateBatchChapters = async () => {
    if (!id) return
    setBatchGenerating(true)
    try {
      const task = await generateBatchChapters(id)
      setError('')
      setActiveTask({ id: task.id, type: 'batch_chapters', progress: 0, status: 'pending' })
      pollTask(
        task.id,
        async () => {
          const chaptersData = await listChapters(id)
          setChapters(chaptersData)
          setBatchGenerating(false)
          setActiveTask(null)
        },
        (msg) => {
          setError(`批量生成失败: ${msg}`)
          setBatchGenerating(false)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建批量生成任务失败')
      setBatchGenerating(false)
      setActiveTask(null)
    }
  }

  const handleGenerateDramaPlan = async () => {
    if (!id) return
    setDramaPlanGenerating(true)
    try {
      const task = await generateDramaPlan(id)
      setError('')
      setActiveTask({ id: task.id, type: 'drama_plan', progress: 0, status: 'pending' })
      pollTask(
        task.id,
        async () => {
          const episodes = await listDramaEpisodes(id)
          setDramaEpisodes(episodes)
          setDramaPlanGenerating(false)
          setActiveTask(null)
        },
        (msg) => {
          setError(`短剧计划生成失败: ${msg}`)
          setDramaPlanGenerating(false)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setDramaPlanGenerating(false)
      setActiveTask(null)
    }
  }

  const handleGenerateDramaEpisode = async (episodeNum: number, chapterNums?: number[]) => {
    if (!id) return
    setGeneratingDramaEpisodeNum(episodeNum)
    try {
      const task = await generateDramaEpisode(id, episodeNum, chapterNums)
      setError('')
      setActiveTask({ id: task.id, type: 'drama_episode', progress: 0, status: 'pending' })
      pollTask(
        task.id,
        async () => {
          const episodes = await listDramaEpisodes(id)
          setDramaEpisodes(episodes)
          setGeneratingDramaEpisodeNum(null)
          setActiveTask(null)
        },
        (msg) => {
          setError(`第${episodeNum}集生成失败: ${msg}`)
          setGeneratingDramaEpisodeNum(null)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建生成任务失败')
      setGeneratingDramaEpisodeNum(null)
      setActiveTask(null)
    }
  }

  const openChapterSelector = (episodeNum: number, defaults: number[]) => {
    setChapterSelectorTarget({ episodeNum, defaults })
    setChapterSelectorSelected(new Set(defaults))
    setShowChapterSelector(true)
  }

  const confirmChapterSelection = () => {
    if (!chapterSelectorTarget) return
    const nums = Array.from(chapterSelectorSelected).sort((a, b) => a - b)
    setShowChapterSelector(false)
    handleGenerateDramaEpisode(chapterSelectorTarget.episodeNum, nums)
  }

  const handleGenerateDramaBatch = async () => {
    if (!id) return
    setBatchDramaGenerating(true)
    try {
      const task = await generateDramaBatch(id)
      setError('')
      setActiveTask({ id: task.id, type: 'drama_batch', progress: 0, status: 'pending' })
      pollTask(
        task.id,
        async () => {
          const episodes = await listDramaEpisodes(id)
          setDramaEpisodes(episodes)
          setBatchDramaGenerating(false)
          setActiveTask(null)
        },
        (msg) => {
          setError(`批量短剧脚本生成失败: ${msg}`)
          setBatchDramaGenerating(false)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建批量生成任务失败')
      setBatchDramaGenerating(false)
      setActiveTask(null)
    }
  }

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  }

  const handleExportEpisode = async (episodeId: string, format: 'json' | 'md' | 'csv') => {
    try {
      const blob = await exportEpisodeScript(episodeId, format)
      const ext = format === 'md' ? 'md' : format
      downloadBlob(blob, `episode_${episodeId.slice(0, 8)}.${ext}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || '导出失败')
    }
  }

  const handleExportAsset = async (assetType: string, format: 'md' | 'json' = 'md') => {
    if (!id) return
    try {
      const blob = await exportAsset(id, assetType, format)
      downloadBlob(blob, `${assetType}.${format}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || '导出失败')
    }
  }

  const handleExportChapters = async (format: 'md' | 'json' = 'md') => {
    if (!id) return
    try {
      const blob = await exportChapters(id, format)
      downloadBlob(blob, `chapters.${format}`)
    } catch (err: any) {
      setError(err.response?.data?.detail || '导出失败')
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

  const pollTask = async (
    taskId: string,
    onSuccess: () => void,
    onError?: (msg: string) => void,
    onProgress?: (progress: number, status: string) => void,
  ) => {
    const interval = setInterval(async () => {
      try {
        const task = await getTask(taskId)
        onProgress?.(task.progress || 0, task.status)
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

  const getTaskStepLabel = (type: string, progress: number): string => {
    const labels: Record<string, Record<number, string>> = {
      architecture: {
        10: '初始化任务...',
        30: '生成核心种子...',
        50: '生成角色动力学...',
        70: '保存角色状态...',
        90: '生成世界观与情节...',
      },
      directory: {
        10: '初始化任务...',
        40: 'LLM 生成章节目录...',
        70: '解析并保存目录...',
      },
      chapter: {
        10: '初始化任务...',
        30: '读取前置资产...',
        50: 'LLM 生成章节正文...',
        80: '保存章节草稿...',
      },
      drama_plan: {
        10: '初始化任务...',
        30: '分析章节分组...',
        60: '生成剧集计划...',
      },
      drama_episode: {
        10: '初始化任务...',
        50: 'LLM 生成单集脚本...',
      },
      batch_chapters: {
        5: '初始化批量任务...',
        10: '读取资产与章节列表...',
        50: '逐章生成正文中...',
        90: '保存最后章节...',
      },
      drama_batch: {
        5: '初始化批量任务...',
        10: '读取剧集与章节列表...',
        50: '逐集生成脚本中...',
        90: '保存最后剧集脚本...',
      },
    }
    const map = labels[type] || {}
    const keys = Object.keys(map).map(Number).sort((a, b) => b - a)
    for (const k of keys) {
      if (progress >= k) return map[k]
    }
    return '处理中...'
  }

  const ProgressBar = ({ progress, label }: { progress: number; label?: string }) => (
    <div className="w-full space-y-1">
      <div className="flex justify-between text-xs text-gray-600">
        <span>{label || '生成中...'}</span>
        <span>{progress}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${Math.max(progress, 5)}%` }}
        ></div>
      </div>
    </div>
  )

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
    <div className="min-h-screen">
      <header className="glass-panel rounded-none border-x-0 border-t-0">
        <div className="max-w-6xl mx-auto py-5 px-6 md:px-10 flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/projects')}
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              ← 返回列表
            </button>
            <h1 className="text-xl font-serif font-medium text-slate-800 tracking-wide">{project.name}</h1>
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

      <main className="max-w-6xl mx-auto py-8 px-6 md:px-10 space-y-6">
        {error && (
          <div className="mb-4 p-4 bg-rose-50/80 text-rose-600 rounded-2xl text-xs text-center font-medium tracking-wide">
            {error}
          </div>
        )}

        {activeTab === 'overview' && (
          <div className="glass-panel p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-base font-serif font-medium text-slate-800">项目信息</h2>
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
        )}

        {activeTab === 'architecture' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-base font-serif font-medium text-slate-800">小说架构</h2>
              <div className="flex space-x-3">
                <button
                  onClick={() => handleExportAsset('architecture')}
                  className="btn-secondary text-[10px] py-1.5 px-3"
                >
                  导出 MD
                </button>
                <button
                  onClick={handleGenerateArchitecture}
                  disabled={architectureGenerating}
                  className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
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
                  onChange={(e) => setArchitectureText(e.target.value)}
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
        )}

        {activeTab === 'directory' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-base font-serif font-medium text-slate-800">章节目录</h2>
              <div className="flex space-x-3">
                <button
                  onClick={() => handleExportAsset('directory')}
                  className="btn-secondary text-[10px] py-1.5 px-3"
                >
                  导出 MD
                </button>
                <button
                  onClick={handleGenerateDirectory}
                  disabled={directoryGenerating}
                  className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
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
                onChange={(e) => setDirectoryText(e.target.value)}
                rows={24}
                className="block w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 font-mono text-sm leading-relaxed"
                placeholder="在此编辑章节目录..."
              />
            )}
          </div>
        )}

        {activeTab === 'chapters' && (
          <div className="glass-panel p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-base font-serif font-medium text-slate-800">章节列表</h2>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleExportChapters('md')}
                  className="btn-secondary text-[10px] py-1.5 px-3"
                >
                  导出 MD
                </button>
                <button
                  onClick={handleGenerateBatchChapters}
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
                      onClick={async () => {
                        try {
                          const blob = await exportChaptersBatch(Array.from(selectedChapterIds), 'md')
                          const url = window.URL.createObjectURL(blob)
                          const a = document.createElement('a')
                          a.href = url
                          a.download = 'chapters_batch.md'
                          document.body.appendChild(a)
                          a.click()
                          a.remove()
                          window.URL.revokeObjectURL(url)
                          setSelectedChapterIds(new Set())
                        } catch (err: any) {
                          setError(err.response?.data?.detail || '导出失败')
                        }
                      }}
                      className="btn-secondary text-[10px] py-1.5 px-3"
                    >
                      导出选中 ({selectedChapterIds.size})
                    </button>
                  )}
                </div>
                <div className="space-y-3">
                {chapters
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
                        <div className="flex items-center space-x-2 ml-4">
                          <button
                            onClick={() => handleGenerateChapter(chapter.chapter_num)}
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
                            onClick={() => handleDeleteChapter(chapter.id)}
                            className="btn-ghost text-rose-400 hover:text-rose-500"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

        {activeTab === 'drama' && (
          <div className="glass-panel p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-base font-serif font-medium text-slate-800">短剧改编</h2>
              <div className="flex items-center space-x-3">
                {dramaEpisodes.length > 0 && (
                  <button
                    onClick={handleGenerateDramaBatch}
                    disabled={batchDramaGenerating}
                    className="btn-primary bg-emerald-700 hover:bg-emerald-800 disabled:opacity-50 disabled:hover:translate-y-0"
                  >
                    {batchDramaGenerating ? '批量生成中...' : 'AI 批量生成全部脚本'}
                  </button>
                )}
                <button
                  onClick={handleGenerateDramaPlan}
                  disabled={dramaPlanGenerating}
                  className="btn-primary disabled:opacity-50 disabled:hover:translate-y-0"
                >
                  {dramaPlanGenerating ? '生成中...' : 'AI 生成改编计划'}
                </button>
              </div>
            </div>
            {activeTask?.type === 'drama_plan' && (
              <ProgressBar
                progress={activeTask.progress}
                label={getTaskStepLabel(activeTask.type, activeTask.progress)}
              />
            )}
            {activeTask?.type === 'drama_episode' && (
              <ProgressBar
                progress={activeTask.progress}
                label={getTaskStepLabel(activeTask.type, activeTask.progress)}
              />
            )}
            {activeTask?.type === 'drama_batch' && (
              <ProgressBar
                progress={activeTask.progress}
                label={getTaskStepLabel(activeTask.type, activeTask.progress)}
              />
            )}

            {dramaLoading ? (
              <p className="text-slate-400 text-xs">加载中...</p>
            ) : dramaEpisodes.length === 0 ? (
              <p className="text-slate-400 text-xs">暂无短剧集，点击上方按钮生成改编计划</p>
            ) : (
              <>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-3">
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={dramaEpisodes.length > 0 && selectedEpisodeIds.size === dramaEpisodes.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedEpisodeIds(new Set(dramaEpisodes.map((ep) => ep.id)))
                        } else {
                          setSelectedEpisodeIds(new Set())
                        }
                      }}
                      className="rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                    />
                    <span className="text-xs text-slate-500">全选</span>
                  </label>
                  {selectedEpisodeIds.size > 0 && (
                    <>
                      <button
                        onClick={async () => {
                          try {
                            const blob = await exportEpisodesBatch(Array.from(selectedEpisodeIds), 'md')
                            const url = window.URL.createObjectURL(blob)
                            const a = document.createElement('a')
                            a.href = url
                            a.download = 'episodes_batch.md'
                            document.body.appendChild(a)
                            a.click()
                            a.remove()
                            window.URL.revokeObjectURL(url)
                            setSelectedEpisodeIds(new Set())
                          } catch (err: any) {
                            setError(err.response?.data?.detail || '导出失败')
                          }
                        }}
                        className="btn-secondary text-[10px] py-1.5 px-3"
                      >
                        导出选中 MD ({selectedEpisodeIds.size})
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            const blob = await exportEpisodesBatch(Array.from(selectedEpisodeIds), 'json')
                            const url = window.URL.createObjectURL(blob)
                            const a = document.createElement('a')
                            a.href = url
                            a.download = 'episodes_batch.json'
                            document.body.appendChild(a)
                            a.click()
                            a.remove()
                            window.URL.revokeObjectURL(url)
                            setSelectedEpisodeIds(new Set())
                          } catch (err: any) {
                            setError(err.response?.data?.detail || '导出失败')
                          }
                        }}
                        className="btn-secondary text-[10px] py-1.5 px-3"
                      >
                        JSON
                      </button>
                    </>
                  )}
                </div>
              </div>
              <div className="space-y-3">
                {dramaEpisodes.map((episode) => (
                  <div
                    key={episode.id}
                    className="glass-panel p-4 card-hover"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex items-start space-x-3 flex-1">
                        <input
                          type="checkbox"
                          checked={selectedEpisodeIds.has(episode.id)}
                          onChange={(e) => {
                            const next = new Set(selectedEpisodeIds)
                            if (e.target.checked) {
                              next.add(episode.id)
                            } else {
                              next.delete(episode.id)
                            }
                            setSelectedEpisodeIds(next)
                          }}
                          className="mt-1 rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                        />
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
                            <p className="mt-2 text-xs text-slate-400">
                              来源：{episode.source_chapters}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 ml-4">
                        <button
                          onClick={() => openChapterSelector(episode.episode_num, episode.source_chapters ? episode.source_chapters.split(',').map((s: string) => parseInt(s.trim())).filter((n: number) => !isNaN(n)) : [])}
                          disabled={generatingDramaEpisodeNum === episode.episode_num}
                          className="text-[10px] font-bold tracking-widest text-emerald-600 hover:text-emerald-700 disabled:opacity-50 transition-colors uppercase"
                        >
                          {generatingDramaEpisodeNum === episode.episode_num ? '生成中...' : '生成脚本'}
                        </button>
                        {(episode.outline_json || episode.script_json) && (
                          <button
                            onClick={() =>
                              setExpandedDramaEpisodeId(
                                expandedDramaEpisodeId === episode.id ? null : episode.id
                              )
                            }
                            className="text-[10px] font-bold tracking-widest text-slate-400 hover:text-slate-700 transition-colors uppercase"
                          >
                            {expandedDramaEpisodeId === episode.id ? '收起脚本' : '查看脚本'}
                          </button>
                        )}
                        {episode.script_json && (
                          <div className="flex items-center space-x-1 ml-1">
                            <span className="text-[10px] text-slate-300 tracking-wider uppercase">导出</span>
                            {(['json', 'md', 'csv'] as const).map((fmt) => (
                              <button
                                key={fmt}
                                onClick={() => handleExportEpisode(episode.id, fmt)}
                                className="text-[10px] font-bold tracking-widest text-slate-400 hover:text-slate-600 transition-colors uppercase"
                                title={`导出 ${fmt.toUpperCase()}`}
                              >
                                {fmt.toUpperCase()}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    {expandedDramaEpisodeId === episode.id && (
                      <div className="mt-3 space-y-3 border-t border-gray-100 pt-3">
                        {episode.outline_json && (
                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-1">分集大纲</h4>
                            <pre className="bg-slate-50/60 rounded-xl p-4 text-[10px] text-slate-600 overflow-x-auto whitespace-pre-wrap border border-white/60">
                              {JSON.stringify(episode.outline_json, null, 2)}
                            </pre>
                          </div>
                        )}
                        {episode.script_json && (
                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-1">脚本详情</h4>
                            <pre className="bg-slate-50/60 rounded-xl p-4 text-[10px] text-slate-600 overflow-x-auto whitespace-pre-wrap border border-white/60">
                              {JSON.stringify(episode.script_json, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div></>
            )}
          </div>
        )}
      {/* Chapter Selector Modal */}
      {showChapterSelector && chapterSelectorTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
          onClick={() => setShowChapterSelector(false)}
        >
          <div
            className="glass-panel p-6 w-full max-w-md mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-serif font-medium text-slate-800 mb-1">
              选择来源章节
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              第{chapterSelectorTarget.episodeNum}集将基于选中的章节生成脚本
            </p>
            <div className="flex items-center justify-between mb-3">
              <label className="flex items-center space-x-2 cursor-pointer"
                onClick={() => {
                  const allNums = chapters.map((c) => c.chapter_num)
                  setChapterSelectorSelected(new Set(allNums))
                }}
              >
                <span className="text-xs text-slate-500 hover:text-slate-700"
                  onClick={() => {
                    const allNums = chapters.map((c) => c.chapter_num)
                    setChapterSelectorSelected(new Set(allNums))
                  }}
                >
                  全选
                </span>
              </label>
              <button
                onClick={() => {
                  if (chapterSelectorTarget.defaults.length > 0) {
                    setChapterSelectorSelected(new Set(chapterSelectorTarget.defaults))
                  } else {
                    setChapterSelectorSelected(new Set())
                  }
                }}
                className="text-[10px] text-slate-400 hover:text-slate-600"
              >
                按默认选择
              </button>
            </div>
            <div className="max-h-64 overflow-y-auto space-y-2 mb-5 border border-white/60 rounded-xl p-3 bg-white/40"
            >
              {chapters.sort((a, b) => a.chapter_num - b.chapter_num).map((chapter) => (
                <label
                  key={chapter.id}
                  className="flex items-center space-x-3 cursor-pointer p-2 rounded-lg hover:bg-white/60 transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={chapterSelectorSelected.has(chapter.chapter_num)}
                    onChange={(e) => {
                      const next = new Set(chapterSelectorSelected)
                      if (e.target.checked) {
                        next.add(chapter.chapter_num)
                      } else {
                        next.delete(chapter.chapter_num)
                      }
                      setChapterSelectorSelected(next)
                    }}
                    className="rounded border-slate-300 text-slate-600 focus:ring-slate-200"
                  />
                  <span className="text-sm text-gray-700">
                    第{chapter.chapter_num}章 {chapter.title}
                  </span>
                </label>
              ))}
            </div>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowChapterSelector(false)}
                className="btn-secondary"
              >
                取消
              </button>
              <button
                onClick={confirmChapterSelection}
                disabled={chapterSelectorSelected.size === 0}
                className="btn-primary disabled:opacity-50"
              >
                确认 ({chapterSelectorSelected.size})
              </button>
            </div>
          </div>
        </div>
      )}
      </main>
    </div>
  )
}

export default ProjectDetail
