import apiClient from './client'

export interface DramaEpisode {
  id: string
  project_id: string
  episode_num: number
  title: string | null
  source_chapters: string | null
  outline_json: Record<string, any> | null
  script_json: Record<string, any> | null
  status: string
  created_at: string
  updated_at: string
}

export const listDramaEpisodes = async (projectId: string): Promise<DramaEpisode[]> => {
  const response = await apiClient.get<DramaEpisode[]>(`/api/projects/${projectId}/drama-episodes`)
  return response.data
}
