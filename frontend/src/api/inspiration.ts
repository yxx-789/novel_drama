import apiClient from './client'

export interface HotNote {
  note_id: string
  title: string
  summary: string | null
  likes: number
  collects: number
  author: string | null
  fetched_at: string
  comment_count?: number
  inspiration_hint?: string | null
  quality_score?: number
}

export const getInspirationCategories = async (): Promise<string[]> => {
  const response = await apiClient.get<string[]>('/api/inspiration/categories')
  return response.data
}

export const getHotNotes = async (category?: string, keyword?: string): Promise<HotNote[]> => {
  const response = await apiClient.get<HotNote[]>('/api/inspiration/hot', {
    params: { category: category || undefined, keyword: keyword || undefined },
  })
  return response.data
}

export const importInspiration = async (
  projectId: string,
  note: HotNote
): Promise<{ success: boolean; topic: string }> => {
  const response = await apiClient.post(`/api/projects/${projectId}/inspiration`, note)
  return response.data
}
