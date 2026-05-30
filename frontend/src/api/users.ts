import { apiClient } from './client'
import type { User, PaginatedResponse } from '@/types/api'
import type { AxiosRequestConfig } from 'axios'

export async function getUsers(
  page = 1,
  pageSize = 50,
  config?: AxiosRequestConfig,
): Promise<PaginatedResponse<User>> {
  const { data } = await apiClient.get<PaginatedResponse<User>>(
    `/api/v1/users?page=${page}&page_size=${pageSize}`,
    config,
  )
  return data
}

export async function createUser(
  payload: { username: string; email: string; password: string; role: string },
  config?: AxiosRequestConfig,
): Promise<User> {
  const { data } = await apiClient.post<User>('/api/v1/users', payload, config)
  return data
}

export async function updateUser(
  userId: string,
  payload: Partial<{ email: string; role: string; is_active: boolean }>,
  config?: AxiosRequestConfig,
): Promise<User> {
  const { data } = await apiClient.patch<User>(`/api/v1/users/${userId}`, payload, config)
  return data
}

export async function deactivateUser(userId: string, config?: AxiosRequestConfig): Promise<void> {
  await apiClient.delete(`/api/v1/users/${userId}`, config)
}
