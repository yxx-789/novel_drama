import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCurrentUser } from '../api/auth'
import { useAuthStore } from '../store/auth'
import type { User } from '../api/auth'

function Dashboard() {
  const navigate = useNavigate()
  const { user, setUser, clearAuth } = useAuthStore()
  const [currentUser, setCurrentUser] = useState<User | null>(user)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const u = await getCurrentUser()
        setCurrentUser(u)
        setUser(u)
      } catch (err: any) {
        const msg = err.response?.data?.detail || '获取用户信息失败'
        setError(msg)
        if (err.response?.status === 401) {
          clearAuth()
          navigate('/login')
        }
      }
    }
    fetchUser()
  }, [navigate, setUser, clearAuth])

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">项目列表</h1>
          <div className="flex items-center space-x-4">
            {currentUser && (
              <span className="text-sm text-gray-600">
                {currentUser.username}
              </span>
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
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}
        <div className="bg-white shadow rounded-lg p-6">
          <p className="text-gray-500">项目列表将在后续开发中实现</p>
        </div>
      </main>
    </div>
  )
}

export default Dashboard
