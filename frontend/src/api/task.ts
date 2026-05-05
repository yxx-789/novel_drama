import apiClient from './client'

export interface Task {
  id: string
  project_id: string
  task_type: string
  status: string
  params: Record<string, any> | null
  result: Record<string, any> | null
  progress: number
  error_msg: string | null
  created_at: string
  updated_at: string
}

export interface CreateTaskRequest {
  task_type: string
  params?: Record<string, any> | null
}

export const createTask = async (projectId: string, data: CreateTaskRequest): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/tasks`, data)
  return response.data
}

export const listTasks = async (projectId: string): Promise<Task[]> => {
  const response = await apiClient.get<Task[]>(`/api/projects/${projectId}/tasks`)
  return response.data
}

export const getTask = async (taskId: string): Promise<Task> => {
  const response = await apiClient.get<Task>(`/api/tasks/${taskId}`)
  return response.data
}
