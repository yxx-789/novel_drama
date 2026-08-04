import apiClient from './client'
import type { Task } from './task'

export const generateArchitecture = async (projectId: string): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/architecture`)
  return response.data
}

export const generateDirectory = async (projectId: string): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/directory`)
  return response.data
}

export const generateChapter = async (projectId: string, chapterNum: number): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/chapter/${chapterNum}`)
  return response.data
}

export const generateDramaPlan = async (projectId: string): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/drama-plan`)
  return response.data
}

export const generateDramaEpisode = async (projectId: string, episodeNum: number, chapterNums?: number[]): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/drama-episode/${episodeNum}`, {
    chapter_nums: chapterNums,
  })
  return response.data
}

export const generateBatchChapters = async (projectId: string): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/chapters/batch`)
  return response.data
}

export const generateDramaBatch = async (projectId: string): Promise<Task> => {
  const response = await apiClient.post<Task>(`/api/projects/${projectId}/generate/drama-batch`)
  return response.data
}
