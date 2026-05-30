// ── Auth ──────────────────────────────────────────────────────
export type Role = 'admin' | 'analyst' | 'auditor'

export interface User {
  id: string
  username: string
  email: string
  role: Role
  is_active: boolean
  created_at: string
  last_login: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  role: Role
}

// ── Fraud / Transactions ──────────────────────────────────────
export type FraudStatus = 'FRAUD' | 'REVIEW' | 'SAFE'

export interface Transaction {
  id: string
  reference: string
  merchant: string
  category: string
  amount: number
  currency: string
  card_number_masked: string
  city: string
  status: FraudStatus
  fraud_score: number | null
  created_at: string
}

export interface TransactionDetail extends Transaction {
  prediction: FraudPrediction | null
  audit_logs: AuditLog[]
}

export interface FraudPrediction {
  id: string
  transaction_id: string
  status: FraudStatus
  fraud_score: number
  model_version: string
  is_reviewed: boolean
  is_confirmed_fraud: boolean | null
  review_notes: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

export interface Alert {
  id: string
  transaction_id: string
  transaction_reference: string
  merchant: string
  amount: number
  fraud_score: number
  is_resolved: boolean
  resolved_by: string | null
  resolved_at: string | null
  notes: string | null
  created_at: string
}

export interface AuditLog {
  id: string
  action: string
  actor: string
  resource_type: string
  resource_id: string
  metadata: Record<string, unknown>
  created_at: string
}

// ── Analytics ────────────────────────────────────────────────
export interface AnalyticsSummary {
  total_transactions: number
  fraud_count: number
  review_count: number
  safe_count: number
  open_alerts: number
  fraud_rate: number
  total_amount: number
  fraud_amount: number
}

export interface FraudRateTrend {
  labels: string[]
  fraud_counts: number[]
  safe_counts: number[]
  review_counts: number[]
  fraud_rates: number[]
}

export interface CategoryBreakdown {
  category: string
  total: number
  fraud: number
  fraud_rate: number
}

export interface TopMerchant {
  merchant: string
  total: number
  fraud: number
  fraud_rate: number
}

// ── Model Registry ───────────────────────────────────────────
export interface ModelInfo {
  id: string
  model_id: string
  name: string
  model_type: string
  status: 'active' | 'deployed' | 'staging' | 'retired' | 'archived'
  metrics: Record<string, number>
  trained_at: string | null
  promoted_at: string | null
  promoted_by: string | null
  created_at: string
}

// ── Pagination ───────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

// ── Predict ──────────────────────────────────────────────────
export interface TransactionInput {
  merchant: string
  category: string
  amt: number
  city: string
  card_number_masked?: string
  hour?: number
  month?: number
}

export interface PredictionResult {
  transaction_id: string
  reference: string
  status: FraudStatus
  fraud_score: number
  model_version: string
  processing_time_ms: number
}

// ── Health ───────────────────────────────────────────────────
export interface HealthStatus {
  status: 'ok' | 'degraded'
  database: string
  redis: string
  ml_model: string
  uptime_seconds: number
}