import { create } from 'zustand'

interface AuthState {
  token: string | null
  user: { id: string; username: string; email: string } | null
  setToken: (token: string) => void
  setUser: (user: { id: string; username: string; email: string }) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: null,
  setToken: (token) => {
    localStorage.setItem('token', token)
    set({ token })
  },
  setUser: (user) => set({ user }),
  clearAuth: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null })
  },
}))
