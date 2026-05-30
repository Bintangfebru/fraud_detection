import { apiClient, API_BASE } from './client'
import type { TokenResponse, User } from '@/types/api'
import type { AxiosRequestConfig } from 'axios'

export async function login(username: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams({ username, password })
  const { data } = await apiClient.post<TokenResponse>('/api/v1/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export async function logout(refreshToken: string): Promise<void> {
  await apiClient.post('/api/v1/auth/logout', { refresh_token: refreshToken })
}

export async function getMe(config?: AxiosRequestConfig): Promise<User> {
  const { data } = await apiClient.get<User>('/api/v1/auth/me', config)
  return data
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiClient.post('/api/v1/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}

export async function refreshAccessToken(refreshToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/api/v1/auth/refresh', {
    refresh_token: refreshToken,
  })
  return data
}
