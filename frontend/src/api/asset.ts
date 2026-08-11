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

export const exportAsset = async (
  projectId: string,
  assetType: string,
  format: 'md' | 'json' = 'md'
): Promise<Blob> => {
  const response = await apiClient.get(`/api/projects/${projectId}/assets/${assetType}/export`, {
    params: { format },
    responseType: 'blob',
  })
  return response.data
}

export interface AssetVersion {
  id: string
  version: number
  trigger_type: 'generate' | 'manual' | 'rollback'
  guidance: string | null
  created_at: string
}

export const getAssetVersions = async (projectId: string, assetType: string): Promise<AssetVersion[]> => {
  const response = await apiClient.get<AssetVersion[]>(`/api/projects/${projectId}/assets/${assetType}/versions`)
  return response.data
}

export const rollbackAsset = async (projectId: string, assetType: string, version: number): Promise<Asset> => {
  const response = await apiClient.post<Asset>(`/api/projects/${projectId}/assets/${assetType}/rollback`, { version })
  return response.data
}
