import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register, getCurrentUser } from '../api/auth'
import { useAuthStore } from '../store/auth'
import { queryClient } from '../queryClient'

function Login() {
  const navigate = useNavigate()
  const { setToken, setUser } = useAuthStore()
  const [isRegister, setIsRegister] = useState(false)
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isRegister) {
        await register({ username, email, password })
        const tokenRes = await login({ username, password })
        setToken(tokenRes.access_token)
      } else {
        const tokenRes = await login({ username, password })
        setToken(tokenRes.access_token)
      }

      const userData = await getCurrentUser()
      setUser(userData)
      queryClient.clear()
      navigate('/projects')
    } catch (err: any) {
      const msg = err.response?.data?.detail || '操作失败，请重试'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="glass-panel w-full max-w-md p-10 md:p-12 space-y-8">
        <div className="text-center space-y-3">
          <h1 className="text-2xl font-serif font-medium text-slate-800 tracking-wide">
            AI 小说 & 短剧创作工作台
          </h1>
          <p className="text-[11px] font-bold text-slate-400 tracking-[0.3em] uppercase">
            {isRegister ? 'Create Account' : 'Welcome Back'}
          </p>
        </div>

        {error && (
          <div className="p-4 bg-rose-50/80 text-rose-600 rounded-2xl text-xs text-center font-medium tracking-wide">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-[10px] font-bold text-slate-400 tracking-widest uppercase mb-2">
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input-glass"
              placeholder="请输入用户名"
              required
            />
          </div>

          {isRegister && (
            <div>
              <label className="block text-[10px] font-bold text-slate-400 tracking-widest uppercase mb-2">
                邮箱
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-glass"
                placeholder="请输入邮箱"
                required
              />
            </div>
          )}

          <div>
            <label className="block text-[10px] font-bold text-slate-400 tracking-widest uppercase mb-2">
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-glass"
              placeholder="请输入密码"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary py-4 disabled:opacity-50 disabled:hover:translate-y-0"
          >
            {loading ? '处理中...' : isRegister ? '注 册' : '登 录'}
          </button>
        </form>

        <div className="text-center pt-2">
          <button
            onClick={() => {
              setIsRegister(!isRegister)
              setError('')
            }}
            className="text-xs text-slate-400 hover:text-slate-600 transition-colors tracking-widest"
          >
            {isRegister ? '已有账号？去登录' : '没有账号？去注册'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Login
