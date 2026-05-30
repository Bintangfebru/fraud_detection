import { apiClient } from './client'
import type {
  Transaction, TransactionDetail, FraudPrediction,
  Alert, PaginatedResponse, TransactionInput, PredictionResult,
} from '@/types/api'
import type { AxiosRequestConfig } from 'axios'

// ── Transactions ─────────────────────────────────────────────

export interface TransactionFilters {
  page?: number
  page_size?: number
  status?: string
  merchant?: string
  start_date?: string
  end_date?: string
}

export async function getTransactions(
  filters: TransactionFilters = {},
  config?: AxiosRequestConfig,
): Promise<PaginatedResponse<Transaction>> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => v != null && params.set(k, String(v)))
  const { data } = await apiClient.get<PaginatedResponse<Transaction>>(
    `/api/v1/fraud/transactions?${params}`,
    config,
  )
  return data
}

export async function getTransactionDetail(
  ref: string,
  config?: AxiosRequestConfig,
): Promise<TransactionDetail> {
  const { data } = await apiClient.get<TransactionDetail>(
    `/api/v1/fraud/transactions/${ref}`,
    config,
  )
  return data
}

// ── Predictions ───────────────────────────────────────────────

export async function predictSingle(
  input: TransactionInput,
  config?: AxiosRequestConfig,
): Promise<PredictionResult> {
  const { data } = await apiClient.post<PredictionResult>(
    '/api/v1/fraud/predict',
    input,
    config,
  )
  return data
}

export async function predictBatch(
  transactions: TransactionInput[],
  config?: AxiosRequestConfig,
): Promise<{ results: PredictionResult[]; total: number }> {
  const { data } = await apiClient.post('/api/v1/fraud/predict/batch', { transactions }, config)
  return data
}

export async function updateReview(
  predictionId: string,
  isConfirmedFraud: boolean,
  notes = '',
  config?: AxiosRequestConfig,
): Promise<FraudPrediction> {
  const { data } = await apiClient.put<FraudPrediction>(
    `/api/v1/fraud/predictions/${predictionId}/review`,
    { is_confirmed_fraud: isConfirmedFraud, review_notes: notes },
    config,
  )
  return data
}

// ── Alerts ────────────────────────────────────────────────────

export async function getAlerts(
  filters: { resolved?: boolean; page?: number } = {},
  config?: AxiosRequestConfig,
): Promise<PaginatedResponse<Alert>> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => v != null && params.set(k, String(v)))
  const { data } = await apiClient.get<PaginatedResponse<Alert>>(
    `/api/v1/fraud/alerts?${params}`,
    config,
  )
  return data
}

export async function resolveAlert(
  alertId: string,
  resolvedBy: string,
  notes = '',
  config?: AxiosRequestConfig,
): Promise<Alert> {
  const { data } = await apiClient.put<Alert>(
    `/api/v1/fraud/alerts/${alertId}/resolve`,
    { resolved_by: resolvedBy, notes },
    config,
  )
  return data
}
