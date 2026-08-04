import apiClient from './client'

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface User {
  id: string
  username: string
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export const login = async (data: LoginRequest): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/api/auth/login', data)
  return response.data
}

export const register = async (data: RegisterRequest): Promise<User> => {
  const response = await apiClient.post<User>('/api/auth/register', data)
  return response.data
}

export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get<User>('/api/auth/me')
  return response.data
}
