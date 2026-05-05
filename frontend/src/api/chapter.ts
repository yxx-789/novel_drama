import apiClient from './client'

export interface Chapter {
  id: string
  project_id: string
  chapter_num: number
  title: string | null
  outline: string | null
  draft: string | null
  finalized_text: string | null
  status: string
  version: number
  created_at: string
  updated_at: string
}

export interface CreateChapterRequest {
  chapter_num: number
  title?: string | null
  outline?: string | null
  draft?: string | null
  finalized_text?: string | null
  status?: string
}

export interface UpdateChapterRequest {
  chapter_num?: number
  title?: string | null
  outline?: string | null
  draft?: string | null
  finalized_text?: string | null
  status?: string
}

export const listChapters = async (projectId: string): Promise<Chapter[]> => {
  const response = await apiClient.get<Chapter[]>(`/api/projects/${projectId}/chapters`)
  return response.data
}

export const createChapter = async (projectId: string, data: CreateChapterRequest): Promise<Chapter> => {
  const response = await apiClient.post<Chapter>(`/api/projects/${projectId}/chapters`, data)
  return response.data
}

export const getChapter = async (chapterId: string): Promise<Chapter> => {
  const response = await apiClient.get<Chapter>(`/api/chapters/${chapterId}`)
  return response.data
}

export const updateChapter = async (chapterId: string, data: UpdateChapterRequest): Promise<Chapter> => {
  const response = await apiClient.put<Chapter>(`/api/chapters/${chapterId}`, data)
  return response.data
}

export const deleteChapter = async (chapterId: string): Promise<void> => {
  await apiClient.delete(`/api/chapters/${chapterId}`)
}
