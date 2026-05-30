import axios, { type AxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor — attach JWT ─────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor — handle 401 ────────────────────────
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      useAuthStore.getState().logout()
    }
    return Promise.reject(error)
  },
)

// ── Helper: cancellable request ───────────────────────────────
export function cancellable<T>(
  fn: (signal: AbortSignal, config: AxiosRequestConfig) => Promise<T>,
): { promise: Promise<T>; cancel: () => void } {
  const controller = new AbortController()
  const promise = fn(controller.signal, { signal: controller.signal })
  return { promise, cancel: () => controller.abort() }
}
