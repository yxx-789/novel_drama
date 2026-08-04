import apiClient from './client'

export interface Project {
  id: string
  name: string
  topic: string | null
  genre: string | null
  num_chapters: number
  word_number: number
  owner_id: string
  status: string
  created_at: string
  updated_at: string
}

export interface CreateProjectRequest {
  name: string
  topic?: string
  genre?: string
  num_chapters?: number
  word_number?: number
}

export interface UpdateProjectRequest {
  name?: string
  topic?: string
  genre?: string
  num_chapters?: number
  word_number?: number
  status?: string
}

export const listProjects = async (): Promise<Project[]> => {
  const response = await apiClient.get<Project[]>('/api/projects')
  return response.data
}

export const createProject = async (data: CreateProjectRequest): Promise<Project> => {
  const response = await apiClient.post<Project>('/api/projects', data)
  return response.data
}

export const getProject = async (id: string): Promise<Project> => {
  const response = await apiClient.get<Project>(`/api/projects/${id}`)
  return response.data
}

export const updateProject = async (id: string, data: UpdateProjectRequest): Promise<Project> => {
  const response = await apiClient.put<Project>(`/api/projects/${id}`, data)
  return response.data
}

export const deleteProject = async (id: string): Promise<void> => {
  await apiClient.delete(`/api/projects/${id}`)
}

export const exportProject = async (id: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/projects/${id}/export`, {
    responseType: 'blob',
  })
  return response.data
}
