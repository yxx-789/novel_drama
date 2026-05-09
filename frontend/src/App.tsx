import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './queryClient'
import Login from './pages/Login'
import ProjectList from './pages/ProjectList'
import ProjectCreate from './pages/ProjectCreate'
import ProjectDetail from './pages/ProjectDetail'
import Toast from './components/Toast'

function RequireAuth() {
  const token = localStorage.getItem('token')
  if (!token) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Toast />
        <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<RequireAuth />}>
          <Route path="/projects" element={<ProjectList />} />
          <Route path="/projects/create" element={<ProjectCreate />} />
          <Route path="/projects/:id" element={<ProjectDetail />} />
          <Route path="/dashboard" element={<Navigate to="/projects" replace />} />
          <Route path="/" element={<Navigate to="/projects" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
