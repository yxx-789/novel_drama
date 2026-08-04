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

export const exportEpisodeScript = async (
  episodeId: string,
  format: 'json' | 'md' | 'csv'
): Promise<Blob> => {
  const response = await apiClient.get(`/api/drama/episodes/${episodeId}/export`, {
    params: { format },
    responseType: 'blob',
  })
  return response.data
}

export const exportEpisodesBatch = async (
  episodeIds: string[],
  format: 'json' | 'md' | 'csv'
): Promise<Blob> => {
  const response = await apiClient.post(`/api/drama/episodes/export/batch`, {
    episode_ids: episodeIds,
  }, {
    params: { format },
    responseType: 'blob',
  })
  return response.data
}

export const updateEpisodeOutline = async (
  episodeId: string,
  outlineJson: Record<string, any>
): Promise<DramaEpisode> => {
  const response = await apiClient.put<DramaEpisode>(`/api/drama/episodes/${episodeId}/outline`, {
    outline_json: outlineJson,
  })
  return response.data
}

export const updateEpisodeScript = async (
  episodeId: string,
  scriptJson: Record<string, any>
): Promise<DramaEpisode> => {
  const response = await apiClient.put<DramaEpisode>(`/api/drama/episodes/${episodeId}/script`, {
    script_json: scriptJson,
  })
  return response.data
}

export const updateSourceChapters = async (
  episodeId: string,
  sourceChapters: string
): Promise<DramaEpisode> => {
  const response = await apiClient.put<DramaEpisode>(`/api/drama/episodes/${episodeId}/source-chapters`, {
    source_chapters: sourceChapters,
  })
  return response.data
}
