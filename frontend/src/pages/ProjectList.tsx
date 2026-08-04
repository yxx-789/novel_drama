import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { listProjects, deleteProject } from '../api/project'
import { getCurrentUser } from '../api/auth'
import { useAuthStore } from '../store/auth'
import { queryClient } from '../queryClient'
import type { Project } from '../api/project'
import AISettingsDrawer from '../components/AISettingsDrawer'

function ProjectList() {
  const navigate = useNavigate()
  const { user, clearAuth } = useAuthStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)

  // 获取当前用户
  useQuery({
    queryKey: ['me'],
    queryFn: getCurrentUser,
    enabled: !user,
    retry: false,
    meta: {
      onError: (err: any) => {
        if (err?.response?.status === 401) {
          clearAuth()
          navigate('/login')
        }
      },
    },
  })

  // 获取项目列表
  const { data: projects = [], isLoading, error } = useQuery({
    queryKey: ['projects'],
    queryFn: listProjects,
  })

  // 删除项目
  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const handleLogout = () => {
    clearAuth()
    queryClient.clear()
    navigate('/login')
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个项目吗？')) return
    deleteMutation.mutate(id)
  }

  const filteredProjects = projects.filter((p: Project) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      p.name.toLowerCase().includes(q) ||
      (p.topic && p.topic.toLowerCase().includes(q)) ||
      (p.genre && p.genre.toLowerCase().includes(q))
    )
  })

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      draft: 'bg-slate-100 text-slate-500',
      generating: 'bg-amber-50 text-amber-600',
      completed: 'bg-emerald-50 text-emerald-600',
    }
    const label: Record<string, string> = {
      draft: '草稿',
      generating: '生成中',
      completed: '已完成',
    }
    return (
      <span className={`text-[10px] px-3 py-1 rounded-full font-bold tracking-wider uppercase ${map[status] || map.draft}`}>
        {label[status] || '草稿'}
      </span>
    )
  }

  return (
    <div className="min-h-screen p-6 md:p-10">
      {/* Header */}
      <header className="max-w-6xl mx-auto mb-10 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-serif font-medium text-slate-800 tracking-wide">我的项目</h1>
          <p className="text-[10px] font-bold text-slate-400 tracking-[0.3em] uppercase mt-1">Project Workspace</p>
        </div>
        <div className="flex items-center space-x-4">
          {user && (
            <span className="text-xs text-slate-400 font-medium">{user.username}</span>
          )}
          <button onClick={() => setSettingsOpen(true)} className="btn-ghost">
            设置
          </button>
          <button onClick={handleLogout} className="btn-ghost">
            退出
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto space-y-6">
        {error && (
          <div className="p-4 bg-rose-50/80 text-rose-600 rounded-2xl text-xs text-center font-medium tracking-wide">
            获取项目列表失败
          </div>
        )}

        <div className="flex items-center space-x-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索项目名称、主题或类型..."
              className="w-full bg-white/80 border border-slate-200 rounded-xl py-2.5 pl-9 pr-4 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-300 transition-all"
            />
            <svg className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <button
            onClick={() => navigate('/projects/create')}
            className="btn-primary whitespace-nowrap"
          >
            + 创建项目
          </button>
        </div>

        <div className="flex justify-between items-center">
          <p className="text-xs text-slate-400 font-medium">
            {searchQuery.trim()
              ? `找到 ${filteredProjects.length} 个匹配项目（共 ${projects.length} 个）`
              : `共 ${projects.length} 个项目`}
          </p>
        </div>

        {isLoading ? (
          <div className="glass-panel p-12 text-center">
            <p className="text-slate-400 text-sm">加载中...</p>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="glass-panel p-16 text-center space-y-4">
            <p className="text-slate-400 text-sm">
              {searchQuery.trim() ? '没有找到匹配的项目' : '还没有项目'}
            </p>
            {!searchQuery.trim() && (
              <p className="text-xs text-slate-300">点击上方按钮开启创作之旅</p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredProjects.map((project: Project) => (
              <div
                key={project.id}
                className="glass-panel p-6 card-hover cursor-pointer group"
                onClick={() => navigate(`/projects/${project.id}`)}
              >
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-base font-serif font-medium text-slate-800 truncate pr-2">
                    {project.name}
                  </h3>
                  {statusBadge(project.status)}
                </div>

                <div className="space-y-1.5 mb-6">
                  {project.topic && (
                    <p className="text-xs text-slate-400">{project.topic}</p>
                  )}
                  {project.genre && (
                    <p className="text-[10px] text-slate-300 tracking-wider uppercase">{project.genre}</p>
                  )}
                </div>

                <div className="pt-4 border-t border-slate-100 flex justify-between items-center">
                  <p className="text-[10px] text-slate-300 tracking-wider">
                    {project.num_chapters} 章 / {project.word_number} 字
                  </p>
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/projects/${project.id}`)
                      }}
                      className="text-[10px] font-bold text-slate-400 hover:text-slate-700 tracking-widest uppercase transition-colors"
                    >
                      查看
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDelete(project.id)
                      }}
                      className="text-[10px] font-bold text-slate-300 hover:text-rose-500 tracking-widest uppercase transition-colors"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <AISettingsDrawer isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}

export default ProjectList
