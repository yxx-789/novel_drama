import apiClient from './client'

export interface LLMConfig {
  api_key: string | null
  base_url: string
  model: string
  source: string
}

export interface LLMConfigUpdate {
  api_key?: string | null
  base_url?: string | null
  model?: string | null
}

export interface LLMConfigTestResult {
  success: boolean
  message: string
}

export async function getLLMConfig(): Promise<LLMConfig> {
  const res = await apiClient.get('/api/user/llm-config')
  return res.data
}

export async function updateLLMConfig(payload: LLMConfigUpdate): Promise<LLMConfig> {
  const res = await apiClient.put('/api/user/llm-config', payload)
  return res.data
}

export async function testLLMConfig(payload?: LLMConfigUpdate): Promise<LLMConfigTestResult> {
  const res = await apiClient.post('/api/user/llm-config/test', payload || {})
  return res.data
}
