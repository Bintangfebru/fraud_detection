import { apiClient } from './client'
import type {
  AnalyticsSummary, FraudRateTrend, CategoryBreakdown,
  TopMerchant, HealthStatus,
} from '@/types/api'
import type { AxiosRequestConfig } from 'axios'

export async function getAnalyticsSummary(config?: AxiosRequestConfig): Promise<AnalyticsSummary> {
  const { data } = await apiClient.get<AnalyticsSummary>('/api/v1/analytics/summary', config)
  return data
}

export async function getFraudRateTrend(
  range: '24h' | '7d' | '30d' = '7d',
  config?: AxiosRequestConfig,
): Promise<FraudRateTrend> {
  const { data } = await apiClient.get<FraudRateTrend>(
    `/api/v1/analytics/fraud-rate?range=${range}`,
    config,
  )
  return data
}

export async function getCategoryBreakdown(config?: AxiosRequestConfig): Promise<CategoryBreakdown[]> {
  const { data } = await apiClient.get<CategoryBreakdown[]>(
    '/api/v1/analytics/category-breakdown',
    config,
  )
  return data
}

export async function getTopMerchants(
  limit = 10,
  config?: AxiosRequestConfig,
): Promise<TopMerchant[]> {
  const { data } = await apiClient.get<TopMerchant[]>(
    `/api/v1/analytics/top-merchants?limit=${limit}`,
    config,
  )
  return data
}

export async function getHealth(config?: AxiosRequestConfig): Promise<HealthStatus> {
  const { data } = await apiClient.get<HealthStatus>('/health', config)
  return data
}
