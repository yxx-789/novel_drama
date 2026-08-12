import axios from 'axios'
import { useToastStore } from '../store/toast'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (status === 401) {
      localStorage.removeItem('token')
      // BASE_URL 生产为 /novel_drama/，dev 为 /，整页跳转带上子路径前缀
      window.location.href = import.meta.env.BASE_URL + 'login'
      useToastStore.getState().addToast('登录已过期，请重新登录', 'warning')
    } else if (status === 403) {
      useToastStore.getState().addToast('无权访问该资源', 'error')
    } else if (status === 404) {
      // Don't auto-toast for 404 — callers often expect missing resources (polling, optional assets)
    } else if (status >= 500) {
      useToastStore.getState().addToast(detail || '服务器错误，请稍后重试', 'error')
    } else if (detail) {
      useToastStore.getState().addToast(detail, 'error')
    }
    return Promise.reject(error)
  }
)

export default apiClient
