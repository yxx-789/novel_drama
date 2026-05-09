import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useToastStore } from '../../store/toast'
import { getProject, updateProject, exportProject } from '../../api/project'
import type { Project } from '../../api/project'
import { listChapters, createChapter, updateChapter, deleteChapter, exportChaptersBatch, exportChapters } from '../../api/chapter'
import type { Chapter, CreateChapterRequest } from '../../api/chapter'
import { getAsset, upsertAsset, exportAsset } from '../../api/asset'
import { listTasks } from '../../api/task'
import {
  generateArchitecture,
  generateDirectory,
  generateChapter,
  generateDramaPlan,
  generateDramaEpisode,
  generateBatchChapters,
  generateDramaBatch,
} from '../../api/generate'
import {
  listDramaEpisodes,
  exportEpisodeScript,
  exportEpisodesBatch,
  updateEpisodeOutline,
  updateSourceChapters,
} from '../../api/drama'
import type { DramaEpisode } from '../../api/drama'
import AIChatDrawer from '../../components/AIChatDrawer'

import OverviewTab from './OverviewTab'
import ArchitectureTab from './ArchitectureTab'
import DirectoryTab from './DirectoryTab'
import ChaptersTab from './ChaptersTab'
import DramaTab from './DramaTab'
import { pollTask, downloadBlob } from './utils'

type TabKey = 'overview' | 'architecture' | 'directory' | 'chapters' | 'drama'

function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [project, setProject] = useState<Project | null>(null)
  const [chapters, setChapters] = useState<Chapter[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const urlTab = searchParams.get('tab') as TabKey
  const initialTab: TabKey = ['overview', 'architecture', 'directory', 'chapters', 'drama'].includes(urlTab)
    ? urlTab
    : 'overview'
  const [activeTab, setActiveTabState] = useState<TabKey>(initialTab)
  const [chatOpen, setChatOpen] = useState(false)

  const [dirty, setDirty] = useState(false)

  const setActiveTab = (tab: TabKey) => {
    if (dirty && tab !== activeTab) {
      if (!confirm('您有未保存的修改，确定要切换吗？')) return
    }
    setActiveTabState(tab)
    setSearchParams({ tab }, { replace: true })
    setError('')
  }

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault()
        e.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  // Overview state
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [name, setName] = useState('')
  const [topic, setTopic] = useState('')
  const [genre, setGenre] = useState('')
  const [numChapters, setNumChapters] = useState(0)
  const [wordNumber, setWordNumber] = useState(0)

  // Architecture state
  const [architectureText, setArchitectureText] = useState('')
  const [characterText, setCharacterText] = useState('')
  const [architectureLoading, setArchitectureLoading] = useState(false)
  const [architectureSaving, setArchitectureSaving] = useState(false)
  const [architectureGenerating, setArchitectureGenerating] = useState(false)

  // Directory state
  const [directoryText, setDirectoryText] = useState('')
  const [directoryLoading, setDirectoryLoading] = useState(false)
  const [directorySaving, setDirectorySaving] = useState(false)
  const [directoryGenerating, setDirectoryGenerating] = useState(false)

  // Chapters state
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
  const [chapterSearchQuery, setChapterSearchQuery] = useState('')

  // Drama state
  const [dramaEpisodes, setDramaEpisodes] = useState<DramaEpisode[]>([])
  const [dramaLoading, setDramaLoading] = useState(false)
  const [dramaPlanGenerating, setDramaPlanGenerating] = useState(false)
  const [batchDramaGenerating, setBatchDramaGenerating] = useState(false)
  const [generatingDramaEpisodeNum, setGeneratingDramaEpisodeNum] = useState<number | null>(null)

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
        if (err.response?.status !== 404) {
          setError(err.response?.data?.detail || '获取架构/人物状态失败')
        }
      } finally {
        setArchitectureLoading(false)
      }
    }
    load()
  }, [activeTab, id])

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
      setDirty(false)
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
      setDirty(false)
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存架构失败')
    } finally {
      setArchitectureSaving(false)
    }
  }

  const handleSaveDirectory = async () => {
    if (!id) return
    setDirectorySaving(true)
    try {
      await upsertAsset(id, 'directory', { content_text: directoryText })
      setDirty(false)
    } catch (err: any) {
      setError(err.response?.data?.detail || '保存目录失败')
    } finally {
      setDirectorySaving(false)
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

  const toast = useToastStore((s) => s.addToast)

  const handleExportEpisode = async (episodeId: string, format: 'json' | 'md' | 'csv') => {
    try {
      const blob = await exportEpisodeScript(episodeId, format)
      const ext = format === 'md' ? 'md' : format
      downloadBlob(blob, `episode_${episodeId.slice(0, 8)}.${ext}`)
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast('该内容尚未生成', 'warning')
      } else {
        setError(err.response?.data?.detail || '导出失败')
      }
    }
  }

  const handleExportEpisodesBatch = async (ids: string[], format: 'md' | 'json') => {
    try {
      return await exportEpisodesBatch(ids, format)
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast('该内容尚未生成', 'warning')
      }
      throw err
    }
  }

  const handleUpdateSourceChapters = async (episodeId: string, sourceChapters: string) => {
    try {
      const updated = await updateSourceChapters(episodeId, sourceChapters)
      setDramaEpisodes((prev) => prev.map((ep) => (ep.id === episodeId ? updated : ep)))
    } catch (err: any) {
      setError(err.response?.data?.detail || '更新来源章节失败')
    }
  }

  const handleUpdateOutline = async (episodeId: string, outlineJson: Record<string, any>) => {
    try {
      const updated = await updateEpisodeOutline(episodeId, outlineJson)
      setDramaEpisodes((prev) => prev.map((ep) => (ep.id === episodeId ? updated : ep)))
    } catch (err: any) {
      setError(err.response?.data?.detail || '更新大纲失败')
    }
  }

  const handleExportAsset = async (assetType: string, format: 'md' | 'json' = 'md') => {
    if (!id) return
    try {
      const blob = await exportAsset(id, assetType, format)
      downloadBlob(blob, `${assetType}.${format}`)
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast('该内容尚未生成，请先使用 AI 生成', 'warning')
      } else {
        setError(err.response?.data?.detail || '导出失败')
      }
    }
  }

  const handleExportChapters = async (format: 'md' | 'json' = 'md') => {
    if (!id) return
    try {
      const blob = await exportChapters(id, format)
      downloadBlob(blob, `chapters.${format}`)
    } catch (err: any) {
      if (err.response?.status === 404) {
        toast('暂无章节可导出', 'warning')
      } else {
        setError(err.response?.data?.detail || '导出失败')
      }
    }
  }

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
      setDirty(false)
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
      setDirty(false)
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
          <div className="flex items-center space-x-2">
            <button
              onClick={async () => {
                if (!id) return
                try {
                  const blob = await exportProject(id)
                  downloadBlob(blob, `${project?.name || 'project'}_export.md`)
                } catch (err: any) {
                  setError(err.response?.data?.detail || '导出失败')
                }
              }}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-50 text-slate-700 text-sm font-medium hover:bg-slate-100 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"
              ><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
              <span>导出项目</span>
            </button>
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 text-sm font-medium hover:bg-indigo-100 transition-colors"
            >
              <span>🤖</span>
              <span>AI 助手</span>
            </button>
          </div>
        </div>
      </header>

      {/* Workflow Progress */}
      <div className="bg-white/60 border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 md:px-10 py-4">
          <div className="flex items-center space-x-2">
            {[
              { key: 'architecture', label: '架构', done: !!architectureText },
              { key: 'directory', label: '目录', done: !!directoryText },
              { key: 'chapters', label: '章节', done: chapters.some((c) => c.status === 'draft_generated' || c.status === 'finalized') },
              { key: 'drama', label: '短剧改编', done: dramaEpisodes.some((ep) => ep.status === 'script_ready') },
            ].map((step, idx, arr) => (
              <div key={step.key} className="flex items-center space-x-2">
                <button
                  onClick={() => {
                    setActiveTab(step.key as TabKey)
                    setError('')
                  }}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    activeTab === step.key
                      ? 'bg-indigo-50 text-indigo-700'
                      : step.done
                        ? 'text-emerald-600 hover:bg-emerald-50'
                        : 'text-slate-400 hover:bg-slate-50'
                  }`}
                >
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                    step.done
                      ? 'bg-emerald-100 text-emerald-600'
                      : activeTab === step.key
                        ? 'bg-indigo-100 text-indigo-600'
                        : 'bg-slate-100 text-slate-400'
                  }`}>
                    {step.done ? '✓' : idx + 1}
                  </span>
                  <span>{step.label}</span>
                </button>
                {idx < arr.length - 1 && (
                  <span className={`w-6 h-px ${step.done ? 'bg-emerald-200' : 'bg-slate-200'}`} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 md:px-10">
          <nav className="-mb-px flex space-x-1" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => {
                  setActiveTab(tab.key)
                  setError('')
                }}
                className={`whitespace-nowrap py-3 px-4 rounded-t-lg border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.key
                    ? 'border-indigo-500 text-indigo-700 bg-indigo-50/50'
                    : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50/50'
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
          <div className="mb-4 p-4 bg-rose-50/80 text-rose-600 rounded-xl text-sm text-center font-medium">
            {error}
          </div>
        )}

        {activeTab === 'overview' && (
          <OverviewTab
            project={project}
            editing={editing}
            setEditing={setEditing}
            saving={saving}
            name={name}
            setName={setName}
            topic={topic}
            setTopic={setTopic}
            genre={genre}
            setGenre={setGenre}
            numChapters={numChapters}
            setNumChapters={setNumChapters}
            wordNumber={wordNumber}
            setWordNumber={setWordNumber}
            setDirty={setDirty}
            onSave={handleSaveProject}
          />
        )}

        {activeTab === 'architecture' && (
          <ArchitectureTab
            architectureText={architectureText}
            setArchitectureText={setArchitectureText}
            characterText={characterText}
            architectureLoading={architectureLoading}
            architectureSaving={architectureSaving}
            architectureGenerating={architectureGenerating}
            activeTask={activeTask}
            setDirty={setDirty}
            onSave={handleSaveArchitecture}
            onGenerate={handleGenerateArchitecture}
            onExport={() => handleExportAsset('architecture')}
          />
        )}

        {activeTab === 'directory' && (
          <DirectoryTab
            directoryText={directoryText}
            setDirectoryText={setDirectoryText}
            directoryLoading={directoryLoading}
            directorySaving={directorySaving}
            directoryGenerating={directoryGenerating}
            activeTask={activeTask}
            setDirty={setDirty}
            onSave={handleSaveDirectory}
            onGenerate={handleGenerateDirectory}
            onExport={() => handleExportAsset('directory')}
          />
        )}

        {activeTab === 'chapters' && (
          <ChaptersTab
            chapters={chapters}
            directoryText={directoryText}
            showAddChapter={showAddChapter}
            setShowAddChapter={setShowAddChapter}
            editingChapterId={editingChapterId}
            setEditingChapterId={setEditingChapterId}
            generatingChapterNum={generatingChapterNum}
            batchGenerating={batchGenerating}
            chapterForm={chapterForm}
            setChapterForm={setChapterForm}
            chapterSearchQuery={chapterSearchQuery}
            setChapterSearchQuery={setChapterSearchQuery}
            selectedChapterIds={selectedChapterIds}
            setSelectedChapterIds={setSelectedChapterIds}
            activeTask={activeTask}
            setDirty={setDirty}
            onAddChapter={handleAddChapter}
            onUpdateChapter={handleUpdateChapter}
            onDeleteChapter={handleDeleteChapter}
            onGenerateChapter={handleGenerateChapter}
            onGenerateBatch={handleGenerateBatchChapters}
            onExport={() => handleExportChapters('md')}
            onExportBatch={(ids) => {
              exportChaptersBatch(ids, 'md')
                .then((blob) => downloadBlob(blob, 'chapters_batch.md'))
                .then(() => setSelectedChapterIds(new Set()))
                .catch((err: any) => {
                  if (err.response?.status === 404) {
                    toast('选中的章节中有没有内容可导出的', 'warning')
                  } else {
                    setError(err.response?.data?.detail || '导出失败')
                  }
                })
            }}
          />
        )}

        {activeTab === 'drama' && (
          <DramaTab
            dramaEpisodes={dramaEpisodes}
            chapters={chapters}
            dramaLoading={dramaLoading}
            dramaPlanGenerating={dramaPlanGenerating}
            batchDramaGenerating={batchDramaGenerating}
            generatingDramaEpisodeNum={generatingDramaEpisodeNum}
            selectedEpisodeIds={selectedEpisodeIds}
            setSelectedEpisodeIds={setSelectedEpisodeIds}
            activeTask={activeTask}
            onGenerateDramaPlan={handleGenerateDramaPlan}
            onGenerateDramaBatch={handleGenerateDramaBatch}
            onExportEpisode={handleExportEpisode}
            onUpdateSourceChapters={handleUpdateSourceChapters}
            onUpdateOutline={handleUpdateOutline}
            onOpenChapterSelector={openChapterSelector}
            onExportEpisodesBatch={handleExportEpisodesBatch}
          />
        )}
      </main>

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

      <AIChatDrawer
        projectId={project.id}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />
    </div>
  )
}

export default ProjectDetail
