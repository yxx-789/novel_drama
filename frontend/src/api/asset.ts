import apiClient from './client'

export interface Asset {
  id: string
  project_id: string
  asset_type: string
  content_text: string | null
  content_json: Record<string, any> | null
  version: number
  updated_at: string
}

export interface UpsertAssetRequest {
  content_text?: string | null
  content_json?: Record<string, any> | null
}

export const getAsset = async (projectId: string, assetType: string): Promise<Asset> => {
  const response = await apiClient.get<Asset>(`/api/projects/${projectId}/assets/${assetType}`)
  return response.data
}

export const upsertAsset = async (projectId: string, assetType: string, data: UpsertAssetRequest): Promise<Asset> => {
  const response = await apiClient.put<Asset>(`/api/projects/${projectId}/assets/${assetType}`, data)
  return response.data
}
