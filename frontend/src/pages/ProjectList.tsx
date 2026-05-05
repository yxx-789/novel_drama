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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">我的项目</h1>
          <div className="flex items-center space-x-4">
            {currentUser && (
              <span className="text-sm text-gray-600">{currentUser.username}</span>
            )}
            <button
              onClick={handleLogout}
              className="text-sm text-red-600 hover:text-red-500"
            >
              退出登录
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">{error}</div>
        )}

        <div className="mb-6 flex justify-between items-center">
          <h2 className="text-lg font-medium text-gray-900">项目列表</h2>
          <button
            onClick={() => navigate('/projects/create')}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700"
          >
            创建项目
          </button>
        </div>

        {loading ? (
          <p className="text-gray-500">加载中...</p>
        ) : projects.length === 0 ? (
          <div className="bg-white shadow rounded-lg p-8 text-center">
            <p className="text-gray-500">还没有项目，点击上方按钮创建一个吧</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <div
                key={project.id}
                className="bg-white shadow rounded-lg p-6 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/projects/${project.id}`)}
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="text-lg font-semibold text-gray-900 truncate">{project.name}</h3>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      project.status === 'draft'
                        ? 'bg-gray-100 text-gray-600'
                        : project.status === 'generating'
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-green-100 text-green-700'
                    }`}
                  >
                    {project.status === 'draft'
                      ? '草稿'
                      : project.status === 'generating'
                      ? '生成中'
                      : '已完成'}
                  </span>
                </div>
                {project.topic && (
                  <p className="text-sm text-gray-500 mb-1">主题：{project.topic}</p>
                )}
                {project.genre && (
                  <p className="text-sm text-gray-500 mb-1">类型：{project.genre}</p>
                )}
                <p className="text-sm text-gray-500">
                  计划 {project.num_chapters} 章 / 每章约 {project.word_number} 字
                </p>
                <div className="mt-4 flex justify-end space-x-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/projects/${project.id}`)
                    }}
                    className="text-sm text-indigo-600 hover:text-indigo-500"
                  >
                    查看
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDelete(project.id)
                    }}
                    className="text-sm text-red-600 hover:text-red-500"
                  >
                    删除
                  </button>
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
