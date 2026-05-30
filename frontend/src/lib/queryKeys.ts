export const queryKeys = {
  // Analytics
  analyticsSummary: ['analytics', 'summary'] as const,
  fraudTrend: (range: string) => ['analytics', 'fraud-trend', range] as const,
  categoryBreakdown: ['analytics', 'category-breakdown'] as const,
  topMerchants: (limit: number) => ['analytics', 'top-merchants', limit] as const,
  health: ['health'] as const,

  // Transactions
  transactions: (filters: Record<string, unknown>) => ['transactions', filters] as const,
  transactionDetail: (ref: string) => ['transactions', 'detail', ref] as const,

  // Alerts
  alerts: (filters: Record<string, unknown>) => ['alerts', filters] as const,

  // Users
  users: (page: number, pageSize: number) => ['users', page, pageSize] as const,

  // Auth
  me: ['auth', 'me'] as const,
}
