import { useQuery } from '@tanstack/react-query'
import { Cpu, CheckCircle, Clock, Archive, TrendingUp, BarChart2, Hash } from 'lucide-react'
import { apiClient } from '@/api/client'
import { type ModelInfo } from '@/types/api'
import { Card, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { ErrorState, EmptyState } from '@/components/ui/ErrorState'
import { Skeleton } from '@/components/ui/Skeleton'
import { formatDate, timeAgo } from '@/utils/format'

async function getModels(): Promise<ModelInfo[]> {
  const { data } = await apiClient.get<{ models: ModelInfo[]; total: number }>('/api/v1/models')
  return data.models ?? []
}

const STATUS_MAP: Record<string, { variant: 'safe' | 'review' | 'neutral'; icon: React.ReactNode }> = {
  active:   { variant: 'safe',    icon: <CheckCircle className="w-3 h-3" /> },
  deployed: { variant: 'safe',    icon: <CheckCircle className="w-3 h-3" /> },
  staging:  { variant: 'review',  icon: <Clock className="w-3 h-3" /> },
  retired:  { variant: 'neutral', icon: <Archive className="w-3 h-3" /> },
  archived: { variant: 'neutral', icon: <Archive className="w-3 h-3" /> },
}

export function Models() {
  const models = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })

  const activeModel = models.data?.find((m) => m.status === 'active' || m.status === 'deployed')

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Active Model Hero ─────────────────────────────────── */}
      {models.isLoading ? (
        <Card className="space-y-4">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-8 w-64" />
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        </Card>
      ) : activeModel ? (
        <Card className="border-sage-100 dark:border-sage-600/20 bg-sage-50/30 dark:bg-sage-600/5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-sage-400 animate-pulse" />
                <span className="text-[10px] font-mono uppercase tracking-wider text-sage-400">
                  Active Production Model
                </span>
              </div>
              <h2 className="font-display font-bold text-2xl text-navy-700 dark:text-warm-100 uppercase tracking-wide">
                {activeModel.name}
              </h2>
              <div className="text-xs font-mono text-warm-500 dark:text-warm-400 mt-0.5">
                {activeModel.model_type} · {activeModel.model_id}
              </div>
            </div>
            <Badge variant="safe" dot>Production</Badge>
          </div>

          {/* Metrics */}
          {activeModel.metrics && Object.keys(activeModel.metrics).length > 0 ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Object.entries(activeModel.metrics).map(([key, value]) => (
                <div
                  key={key}
                  className="bg-warm-50 dark:bg-navy-800 rounded-lg p-3 border border-warm-200 dark:border-navy-700"
                >
                  <div className="text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1">
                    {key.replace(/_/g, ' ')}
                  </div>
                  <div className="font-display font-bold text-xl text-navy-700 dark:text-warm-200">
                    {typeof value === 'number' && value <= 1
                      ? `${(value * 100).toFixed(1)}%`
                      : value}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs font-mono text-warm-400">No metrics recorded</div>
          )}

          <div className="flex gap-4 mt-4 text-xs font-mono text-warm-500 dark:text-warm-400">
            {activeModel.trained_at && (
              <span>Trained {timeAgo(activeModel.trained_at)}</span>
            )}
            {activeModel.promoted_at && (
              <span>Promoted {timeAgo(activeModel.promoted_at)} by {activeModel.promoted_by}</span>
            )}
          </div>
        </Card>
      ) : null}

      {/* ── All Models ───────────────────────────────────────── */}
      <Card noPad>
        <div className="p-5">
          <CardHeader
            title="Model Registry"
            subtitle={models.data ? `${models.data.length} models` : '—'}
            action={
              <div className="flex items-center gap-1.5 text-xs font-mono text-warm-500 dark:text-warm-400">
                <Cpu className="w-3.5 h-3.5" />
                <span>ML Model Manager</span>
              </div>
            }
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['Model', 'Type', 'Status', 'Key Metrics', 'Trained', 'Promoted By', ''].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {models.isLoading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-warm-200/60 dark:border-navy-700/50">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <Skeleton className="h-4 w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : models.isError ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12">
                    <ErrorState message="Failed to load models" onRetry={() => models.refetch()} />
                  </td>
                </tr>
              ) : models.data?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12">
                    <EmptyState
                      icon={<Cpu className="w-6 h-6" />}
                      title="No models registered"
                    />
                  </td>
                </tr>
              ) : (
                models.data?.map((model) => {
                  const statusInfo = STATUS_MAP[model.status] ?? STATUS_MAP.archived
                  const topMetrics = Object.entries(model.metrics ?? {}).slice(0, 2)
                  return (
                    <tr
                      key={model.id}
                      className="border-b border-warm-200/60 dark:border-navy-700/50 hover:bg-warm-100 dark:hover:bg-navy-700/30 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <div className="font-semibold text-navy-700 dark:text-warm-200">{model.name}</div>
                        <div className="text-warm-400 text-[10px]">{model.model_id}</div>
                      </td>
                      <td className="px-4 py-3 text-warm-500 dark:text-warm-400 uppercase">
                        {model.model_type}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={statusInfo.variant} dot>
                          {model.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-0.5">
                          {topMetrics.length > 0 ? (
                            topMetrics.map(([k, v]) => (
                              <span key={k} className="text-[10px]">
                                <span className="text-warm-400">{k.replace(/_/g, ' ')}: </span>
                                <span className="text-navy-700 dark:text-warm-200 font-semibold">
                                  {typeof v === 'number' && v <= 1
                                    ? `${(v * 100).toFixed(1)}%`
                                    : v}
                                </span>
                              </span>
                            ))
                          ) : (
                            <span className="text-warm-400">—</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-warm-500 dark:text-warm-400">
                        {model.trained_at ? timeAgo(model.trained_at) : '—'}
                      </td>
                      <td className="px-4 py-3 text-warm-500 dark:text-warm-400">
                        {model.promoted_by ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <span className="text-[10px] font-mono text-warm-400">
                            {model.promoted_at ? formatDate(model.promoted_at) : '—'}
                          </span>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Performance Overview ─────────────────────────────── */}
      {activeModel?.metrics && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Precision', key: 'precision', icon: <BarChart2 className="w-5 h-5" />, accent: 'text-sage-400' },
            { label: 'Recall', key: 'recall', icon: <TrendingUp className="w-5 h-5" />, accent: 'text-navy-700 dark:text-warm-200' },
            { label: 'F1 Score', key: 'f1_score', icon: <Hash className="w-5 h-5" />, accent: 'text-amber-400' },
            { label: 'AUC-ROC', key: 'roc_auc', icon: <TrendingUp className="w-5 h-5" />, accent: 'text-sage-400' },
          ].map(({ label, key, icon, accent }) => {
            const val = activeModel.metrics?.[key]
            if (val == null) return null
            return (
              <Card key={key} className="p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className={accent}>{icon}</span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400">
                    {label}
                  </span>
                </div>
                <div className={`font-display font-bold text-3xl ${accent}`}>
                  {(val * 100).toFixed(1)}%
                </div>
                <div className="mt-2 h-1.5 bg-warm-300 dark:bg-navy-700 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-sage-400 transition-all"
                    style={{ width: `${val * 100}%` }}
                  />
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}