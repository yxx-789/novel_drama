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
    <div className="min-h-screen p-6 md:p-10">
      <header className="max-w-6xl mx-auto mb-10 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-serif font-medium text-slate-800 tracking-wide">工作台</h1>
          <p className="text-[10px] font-bold text-slate-400 tracking-[0.3em] uppercase mt-1">Dashboard</p>
        </div>
        <div className="flex items-center space-x-4">
          {currentUser && (
            <span className="text-xs text-slate-400 font-medium">{currentUser.username}</span>
          )}
          <button onClick={handleLogout} className="btn-ghost">退出</button>
        </div>
      </header>
      <main className="max-w-6xl mx-auto space-y-6">
        {error && (
          <div className="p-4 bg-rose-50/80 text-rose-600 rounded-2xl text-xs text-center font-medium tracking-wide">
            {error}
          </div>
        )}
        <div className="glass-panel p-16 text-center space-y-4">
          <p className="text-slate-400 text-sm">欢迎回来，{currentUser?.username || '创作者'}</p>
          <button onClick={() => navigate('/projects')} className="btn-primary">
            进入项目列表
          </button>
        </div>
      </main>
    </div>
  )
}

export default Dashboard
