import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, deleteProject } from '../api/project'
import { getCurrentUser } from '../api/auth'
import { useAuthStore } from '../store/auth'
import type { Project } from '../api/project'
import type { User } from '../api/auth'

function ProjectList() {
  const navigate = useNavigate()
  const { user, setUser, clearAuth } = useAuthStore()
  const [currentUser, setCurrentUser] = useState<User | null>(user)
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const init = async () => {
      try {
        const u = await getCurrentUser()
        setCurrentUser(u)
        setUser(u)
      } catch (err: any) {
        if (err.response?.status === 401) {
          clearAuth()
          navigate('/login')
          return
        }
      }

      try {
        const data = await listProjects()
        setProjects(data)
      } catch (err: any) {
        setError(err.response?.data?.detail || '获取项目列表失败')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [navigate, setUser, clearAuth])

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个项目吗？')) return
    try {
      await deleteProject(id)
      setProjects(projects.filter((p) => p.id !== id))
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除失败')
    }
  }

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
          {currentUser && (
            <span className="text-xs text-slate-400 font-medium">{currentUser.username}</span>
          )}
          <button onClick={handleLogout} className="btn-ghost">
            退出
          </button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto space-y-6">
        {error && (
          <div className="p-4 bg-rose-50/80 text-rose-600 rounded-2xl text-xs text-center font-medium tracking-wide">
            {error}
          </div>
        )}

        <div className="flex justify-between items-center">
          <p className="text-xs text-slate-400 font-medium">
            共 {projects.length} 个项目
          </p>
          <button
            onClick={() => navigate('/projects/create')}
            className="btn-primary"
          >
            + 创建项目
          </button>
        </div>

        {loading ? (
          <div className="glass-panel p-12 text-center">
            <p className="text-slate-400 text-sm">加载中...</p>
          </div>
        ) : projects.length === 0 ? (
          <div className="glass-panel p-16 text-center space-y-4">
            <p className="text-slate-400 text-sm">还没有项目</p>
            <p className="text-[10px] text-slate-300 tracking-widest uppercase">点击上方按钮开启创作之旅</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((project) => (
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
    </div>
  )
}

export default ProjectList
