import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useToastStore } from '../../store/toast'
import { exportProject } from '../../api/project'
import { exportChaptersBatch, exportChapters } from '../../api/chapter'
import type { CreateChapterRequest } from '../../api/chapter'
import { exportAsset } from '../../api/asset'
import { listTasks, getTask } from '../../api/task'
import {
  generateArchitecture,
  generateDirectory,
  generateChapter,
  generateDramaPlan,
  generateDramaEpisode,
  generateBatchChapters,
  generateDramaBatch,
  generateContinueWriting,
} from '../../api/generate'
import {
  exportEpisodeScript,
  exportEpisodesBatch,
} from '../../api/drama'
import AIChatDrawer from '../../components/AIChatDrawer'

import OverviewTab from './OverviewTab'
import ArchitectureTab from './ArchitectureTab'
import DirectoryTab from './DirectoryTab'
import WorldStateTab from './WorldStateTab'
import ChaptersTab from './ChaptersTab'
import DramaTab from './DramaTab'
import InspirationTab from './InspirationTab'
import { pollTask, downloadBlob } from './utils'
import { useProjectData } from './useProjectData'
import { queryClient } from '../../queryClient'

type TabKey = 'overview' | 'architecture' | 'directory' | 'chapters' | 'drama' | 'worldstate' | 'inspiration'

function ProjectDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const {
    project,
    projectLoading,
    projectError,
    chapters,
    architecture,
    characters,
    directory,
    dramaEpisodes,
    architectureLoading,
    directoryLoading,
    dramaLoading,
    saveProject,
    saveAsset,
    addChapter,
    updateChapter,
    deleteChapter,
    updateEpisode,
    updateSource,
  } = useProjectData(id)

  const urlTab = searchParams.get('tab') as TabKey
  const initialTab: TabKey = ['overview', 'architecture', 'directory', 'chapters', 'drama', 'worldstate', 'inspiration'].includes(urlTab)
    ? urlTab
    : 'overview'
  const [activeTab, setActiveTabState] = useState<TabKey>(initialTab)
  const [chatOpen, setChatOpen] = useState(false)

  const [dirty, setDirty] = useState(false)

  const setActiveTab = (tab: TabKey) => {
    if (dirty && tab !== activeTab) {
      if (!confirm('您有未保存的修改，确定要切换吗？')) return
      setDirty(false)
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
  const [name, setName] = useState('')
  const [topic, setTopic] = useState('')
  const [genre, setGenre] = useState('')
  const [numChapters, setNumChapters] = useState(0)
  const [wordNumber, setWordNumber] = useState(0)
  const [storyShape, setStoryShape] = useState<string>('final')
  const [totalChaptersTarget, setTotalChaptersTarget] = useState<number | null>(null)

  // Architecture state
  const [architectureText, setArchitectureText] = useState('')
  const [architectureSaving, setArchitectureSaving] = useState(false)
  const [architectureGenerating, setArchitectureGenerating] = useState(false)

  // Directory state
  const [directoryText, setDirectoryText] = useState('')
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
  const [selectedChapterIds, setSelectedChapterIds] = useState<Set<string>>(new Set())

  // Drama state
  const [dramaPlanGenerating, setDramaPlanGenerating] = useState(false)
  const [batchDramaGenerating, setBatchDramaGenerating] = useState(false)
  const [generatingDramaEpisodeNum, setGeneratingDramaEpisodeNum] = useState<number | null>(null)
  const [selectedEpisodeIds, setSelectedEpisodeIds] = useState<Set<string>>(new Set())

  // Chapter selector modal state
  const [showChapterSelector, setShowChapterSelector] = useState(false)
  const [chapterSelectorTarget, setChapterSelectorTarget] = useState<{ episodeNum: number; defaults: number[] } | null>(null)
  const [chapterSelectorSelected, setChapterSelectorSelected] = useState<Set<number>>(new Set())

  // Active task progress tracking
  const [activeTask, setActiveTask] = useState<{ id: string; type: string; progress: number; status: string } | null>(null)
  const pollCleanupRef = useRef<(() => void) | null>(null)
  const [error, setError] = useState('')

  // Sync query data to local editing state (only when not dirty)
  useEffect(() => {
    if (project && !dirty) {
      setName(project.name)
      setTopic(project.topic || '')
      setGenre(project.genre || '')
      setNumChapters(project.num_chapters)
      setWordNumber(project.word_number)
      setStoryShape(project.story_shape || 'final')
      setTotalChaptersTarget(project.total_chapters_target ?? null)
    }
  }, [project, dirty])

  useEffect(() => {
    if (architecture && !dirty) {
      setArchitectureText(architecture.content_text || '')
    }
  }, [architecture, dirty])

  useEffect(() => {
    if (directory && !dirty) {
      setDirectoryText(directory.content_text || '')
    }
  }, [directory, dirty])

  // Recover running tasks on mount
  useEffect(() => {
    if (!id) return
    const recoverTask = async () => {
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
          } else if (runningTask.task_type === 'continue_writing') {
            setDirectoryGenerating(true)
            setActiveTask({ id: runningTask.id, type: 'continue_writing', progress: runningTask.progress, status: runningTask.status })
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
          pollCleanupRef.current?.()
          pollCleanupRef.current = pollTask(
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
                queryClient.invalidateQueries({ queryKey: ['asset', id, 'architecture'] })
                queryClient.invalidateQueries({ queryKey: ['asset', id, 'characters'] })
              } else if (runningTask.task_type === 'directory' && id) {
                queryClient.invalidateQueries({ queryKey: ['asset', id, 'directory'] })
                queryClient.invalidateQueries({ queryKey: ['chapters', id] })
              } else if (runningTask.task_type === 'continue_writing' && id) {
                queryClient.invalidateQueries({ queryKey: ['asset', id, 'directory'] })
                queryClient.invalidateQueries({ queryKey: ['chapters', id] })
                queryClient.invalidateQueries({ queryKey: ['project', id] })
                setDirectoryGenerating(false)
                setActiveTask(null)
              } else if ((runningTask.task_type === 'chapter' || runningTask.task_type === 'batch_chapters') && id) {
                queryClient.invalidateQueries({ queryKey: ['chapters', id] })
              } else if (runningTask.task_type.startsWith('drama') && id) {
                queryClient.invalidateQueries({ queryKey: ['dramaEpisodes', id] })
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
    }
    recoverTask()
    return () => {
      pollCleanupRef.current?.()
      pollCleanupRef.current = null
    }
  }, [id])

  const handleSaveProject = async () => {
    if (!id) return
    saveProject.mutate(
      {
        name,
        topic: topic || undefined,
        genre: genre || undefined,
        num_chapters: numChapters,
        word_number: wordNumber,
        story_shape: storyShape,
        total_chapters_target: storyShape === 'open' ? totalChaptersTarget : undefined,
      },
      {
        onSuccess: () => {
          setEditing(false)
          setDirty(false)
        },
        onError: (err: any) => {
          setError(err.response?.data?.detail || '保存失败')
        },
      }
    )
  }

  const handleSaveArchitecture = async () => {
    if (!id) return
    setArchitectureSaving(true)
    saveAsset.mutate(
      { assetType: 'architecture', data: { content_text: architectureText } },
      {
        onSuccess: () => {
          setDirty(false)
          setArchitectureSaving(false)
        },
        onError: (err: any) => {
          setError(err.response?.data?.detail || '保存架构失败')
          setArchitectureSaving(false)
        },
      }
    )
  }

  const handleSaveDirectory = async () => {
    if (!id) return
    setDirectorySaving(true)
    saveAsset.mutate(
      { assetType: 'directory', data: { content_text: directoryText } },
      {
        onSuccess: () => {
          setDirty(false)
          setDirectorySaving(false)
        },
        onError: (err: any) => {
          setError(err.response?.data?.detail || '保存目录失败')
          setDirectorySaving(false)
        },
      }
    )
  }

  const handleGenerateArchitecture = async (guidance?: string) => {
    if (!id) return
    setArchitectureGenerating(true)
    try {
      const task = await generateArchitecture(id, guidance)
      setError('')
      setActiveTask({ id: task.id, type: 'architecture', progress: 0, status: 'pending' })
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['asset', id, 'architecture'] })
          queryClient.invalidateQueries({ queryKey: ['asset', id, 'characters'] })
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

  const handleGenerateDirectory = async (guidance?: string) => {
    if (!id) return
    setDirectoryGenerating(true)
    try {
      const task = await generateDirectory(id, guidance)
      setError('')
      setActiveTask({ id: task.id, type: 'directory', progress: 0, status: 'pending' })
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['asset', id, 'directory'] })
          queryClient.invalidateQueries({ queryKey: ['chapters', id] })
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

  const handleContinueWriting = async (k: number) => {
    if (!id) return
    setDirectoryGenerating(true)
    try {
      const task = await generateContinueWriting(id, k)
      setError('')
      setActiveTask({ id: task.id, type: 'continue_writing', progress: 0, status: 'pending' })
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['asset', id, 'directory'] })
          queryClient.invalidateQueries({ queryKey: ['chapters', id] })
          queryClient.invalidateQueries({ queryKey: ['project', id] })
          setDirectoryGenerating(false)
          setActiveTask(null)
        },
        (msg) => {
          setError(`续写失败: ${msg}`)
          setDirectoryGenerating(false)
          setActiveTask(null)
        },
        (progress, status) => {
          setActiveTask((prev) => (prev ? { ...prev, progress, status } : null))
        }
      )
    } catch (err: any) {
      setError(err.response?.data?.detail || '创建续写任务失败')
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
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['chapters', id] })
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
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['chapters', id] })
          setBatchGenerating(false)
          setActiveTask(null)
          // 检查是否有失败章节
          try {
            const finalTask = await getTask(task.id)
            const failed = finalTask.result?.failed_chapters as Array<{ chapter_num: number; error: string }> | undefined
            if (failed && failed.length > 0) {
              const nums = failed.map((f) => f.chapter_num).join(', ')
              toast(`批量生成完成，但第 ${nums} 章生成失败`, 'warning')
            } else {
              toast('批量生成全部完成', 'success')
            }
          } catch {
            // ignore
          }
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
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['dramaEpisodes', id] })
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
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['dramaEpisodes', id] })
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
    const nums = [...chapterSelectorSelected].sort((a, b) => a - b)
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
      pollCleanupRef.current?.()
      pollCleanupRef.current = pollTask(
        task.id,
        async () => {
          queryClient.invalidateQueries({ queryKey: ['dramaEpisodes', id] })
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
    updateSource.mutate(
      { episodeId, sourceChapters },
      {
        onError: (err: any) => setError(err.response?.data?.detail || '更新来源章节失败'),
      }
    )
  }

  const handleUpdateOutline = async (episodeId: string, outlineJson: Record<string, any>) => {
    updateEpisode.mutate(
      { episodeId, outlineJson },
      {
        onError: (err: any) => setError(err.response?.data?.detail || '更新大纲失败'),
      }
    )
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
    addChapter.mutate(chapterForm, {
      onSuccess: () => {
        setShowAddChapter(false)
        setDirty(false)
        resetChapterForm()
      },
      onError: (err: any) => setError(err.response?.data?.detail || '创建章节失败'),
    })
  }

  const handleUpdateChapter = async (chapterId: string) => {
    updateChapter.mutate(
      { chapterId, data: chapterForm },
      {
        onSuccess: () => {
          setEditingChapterId(null)
          setDirty(false)
          resetChapterForm()
        },
        onError: (err: any) => setError(err.response?.data?.detail || '更新章节失败'),
      }
    )
  }

  const handleDeleteChapter = async (chapterId: string) => {
    if (!window.confirm('确定要删除这个章节吗？')) return
    deleteChapter.mutate(chapterId, {
      onError: (err: any) => setError(err.response?.data?.detail || '删除章节失败'),
    })
  }

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'overview', label: '概览' },
    { key: 'architecture', label: '架构' },
    { key: 'directory', label: '目录' },
    { key: 'chapters', label: '章节' },
    { key: 'drama', label: '短剧改编' },
    { key: 'worldstate', label: '角色与世界' },
    { key: 'inspiration', label: '创作灵感' },
  ]

  if (projectLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">加载中...</p>
      </div>
    )
  }

  if (projectError) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-500">{projectError.message || '获取数据失败'}</p>
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
              { key: 'architecture', label: '架构', done: !!(architecture?.content_text) },
              { key: 'directory', label: '目录', done: !!(directory?.content_text) },
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

      <main className={`mx-auto py-8 space-y-6 ${activeTab === 'chapters' ? 'max-w-[1400px] px-4' : 'max-w-6xl px-6 md:px-10'}`}>
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
            saving={saveProject.isPending}
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
            storyShape={storyShape}
            setStoryShape={setStoryShape}
            totalChaptersTarget={totalChaptersTarget}
            setTotalChaptersTarget={setTotalChaptersTarget}
            setDirty={setDirty}
            onSave={handleSaveProject}
          />
        )}

        {activeTab === 'architecture' && (
          <ArchitectureTab
            value={architectureText}
            onChange={(v) => { setArchitectureText(v); setDirty(true) }}
            characterText={characters?.content_text || ''}
            loading={architectureLoading}
            saving={architectureSaving}
            generating={architectureGenerating}
            activeTask={activeTask}
            projectId={project!.id}
            currentVersion={architecture?.version ?? 0}
            onSave={handleSaveArchitecture}
            onGenerate={handleGenerateArchitecture}
            onExport={() => handleExportAsset('architecture')}
          />
        )}

        {activeTab === 'directory' && (
          <DirectoryTab
            value={directoryText}
            onChange={(v) => { setDirectoryText(v); setDirty(true) }}
            loading={directoryLoading}
            saving={directorySaving}
            generating={directoryGenerating}
            activeTask={activeTask}
            projectId={project!.id}
            currentVersion={directory?.version ?? 0}
            onSave={handleSaveDirectory}
            onGenerate={handleGenerateDirectory}
            onExport={() => handleExportAsset('directory')}
            canContinue={project!.story_shape === 'open' && (!project!.total_chapters_target || project!.num_chapters < project!.total_chapters_target)}
            totalChaptersTarget={project!.total_chapters_target}
            numChapters={project!.num_chapters}
            onContinue={handleContinueWriting}
          />
        )}

        {activeTab === 'chapters' && (
          <ChaptersTab
            chapters={chapters}
            directoryText={directory?.content_text || ''}
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

        {activeTab === 'worldstate' && (
          <WorldStateTab projectId={project!.id} chapters={chapters.map(c => ({ id: c.id, chapter_num: c.chapter_num, title: c.title }))} />
        )}

        {activeTab === 'inspiration' && (
          <InspirationTab projectId={project!.id} />
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
