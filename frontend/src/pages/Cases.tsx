import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FolderOpen, CheckCircle, XCircle, Clock, Filter } from 'lucide-react'
import { getAlerts, resolveAlert } from '@/api/fraud'
import { queryKeys } from '@/lib/queryKeys'
import { Card, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { ErrorState, EmptyState } from '@/components/ui/ErrorState'
import { TableRowSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { formatCurrency, formatDate, formatScore } from '@/utils/format'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'

export function Cases() {
  const queryClient = useQueryClient()
  const user = useAuthStore((s) => s.user)
  const can = useAuthStore((s) => s.can)

  const [showResolved, setShowResolved] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')

  const alerts = useQuery({
    queryKey: queryKeys.alerts({ resolved: showResolved }),
    queryFn: ({ signal }) => getAlerts({ resolved: showResolved }, { signal }),
  })

  const resolveMutation = useMutation({
    mutationFn: (alertId: string) =>
      resolveAlert(alertId, user?.username ?? 'system', notes),
    onSuccess: () => {
      toast.success('Alert resolved')
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      setSelectedId(null)
      setNotes('')
    },
    onError: () => toast.error('Failed to resolve alert'),
  })

  const openAlert = alerts.data?.items.find((a) => a.id === selectedId)

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── Header Stats ─────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            label: 'Open Cases',
            value: alerts.data?.items.filter((a) => !a.is_resolved).length ?? '—',
            icon: <Clock className="w-5 h-5" />,
            accent: 'text-amber-400',
            bg: 'bg-amber-50 dark:bg-amber-600/10',
          },
          {
            label: 'Total Alerts',
            value: alerts.data?.total ?? '—',
            icon: <FolderOpen className="w-5 h-5" />,
            accent: 'text-navy-700 dark:text-warm-200',
            bg: 'bg-warm-200 dark:bg-navy-700',
          },
          {
            label: 'Resolved',
            value: alerts.data?.items.filter((a) => a.is_resolved).length ?? '—',
            icon: <CheckCircle className="w-5 h-5" />,
            accent: 'text-sage-400',
            bg: 'bg-sage-50 dark:bg-sage-600/10',
          },
        ].map(({ label, value, icon, accent, bg }) => (
          <Card key={label} className="flex items-center gap-4">
            <div className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${bg}`}>
              <span className={accent}>{icon}</span>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400">
                {label}
              </div>
              <div className={`font-display font-bold text-3xl leading-none ${accent}`}>{value}</div>
            </div>
          </Card>
        ))}
      </div>

      {/* ── Filters ───────────────────────────────────────────── */}
      <Card className="flex items-center gap-3">
        <Filter className="w-4 h-4 text-warm-400" />
        <div className="flex gap-1">
          {[
            { label: 'Open Cases', value: false },
            { label: 'Resolved', value: true },
          ].map(({ label, value }) => (
            <button
              key={label}
              onClick={() => setShowResolved(value)}
              className={`px-3 py-1.5 text-xs font-mono rounded transition-colors ${
                showResolved === value
                  ? 'bg-navy-700 text-warm-100 dark:bg-coral-400 dark:text-white'
                  : 'text-warm-500 hover:text-navy-700 dark:hover:text-warm-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="ml-auto text-xs font-mono text-warm-500 dark:text-warm-400">
          {alerts.data ? `${alerts.data.total} records` : '—'}
        </div>
      </Card>

      {/* ── Alert Table ───────────────────────────────────────── */}
      <Card noPad>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['Reference', 'Merchant', 'Amount', 'Risk Score', 'Created', 'Status', ''].map((h) => (
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
              {alerts.isLoading ? (
                Array.from({ length: 8 }).map((_, i) => <TableRowSkeleton key={i} cols={7} />)
              ) : alerts.isError ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12">
                    <ErrorState message="Failed to load cases" onRetry={() => alerts.refetch()} />
                  </td>
                </tr>
              ) : alerts.data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12">
                    <EmptyState
                      icon={<FolderOpen className="w-6 h-6" />}
                      title="No cases found"
                      description={showResolved ? 'No resolved cases' : 'No open cases — great work!'}
                    />
                  </td>
                </tr>
              ) : (
                alerts.data?.items.map((alert) => (
                  <tr
                    key={alert.id}
                    className="border-b border-warm-200/60 dark:border-navy-700/50 hover:bg-warm-100 dark:hover:bg-navy-700/30 transition-colors"
                  >
                    <td className="px-4 py-2.5 font-semibold text-navy-700 dark:text-warm-200">
                      {alert.transaction_reference}
                    </td>
                    <td className="px-4 py-2.5 text-warm-600 dark:text-warm-400 max-w-[120px] truncate">
                      {alert.merchant}
                    </td>
                    <td className="px-4 py-2.5 text-navy-700 dark:text-warm-200">
                      {formatCurrency(alert.amount)}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`font-bold ${
                          alert.fraud_score > 0.7
                            ? 'text-coral-400'
                            : alert.fraud_score > 0.4
                            ? 'text-amber-400'
                            : 'text-sage-400'
                        }`}
                      >
                        {formatScore(alert.fraud_score)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400 whitespace-nowrap">
                      {formatDate(alert.created_at)}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge variant={alert.is_resolved ? 'safe' : 'review'} dot>
                        {alert.is_resolved ? 'Resolved' : 'Open'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2.5">
                      {!alert.is_resolved && can('approve_review') && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedId(alert.id)}
                        >
                          Review
                        </Button>
                      )}
                      {alert.is_resolved && (
                        <span className="text-[10px] font-mono text-warm-400">
                          by {alert.resolved_by}
                        </span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Review Modal ─────────────────────────────────────── */}
      <Modal
        open={!!selectedId && !!openAlert}
        onClose={() => { setSelectedId(null); setNotes('') }}
        title="Resolve Alert"
        subtitle={openAlert?.transaction_reference}
        footer={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => { setSelectedId(null); setNotes('') }}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={resolveMutation.isPending}
              icon={<XCircle className="w-3.5 h-3.5" />}
              onClick={() => selectedId && resolveMutation.mutate(selectedId)}
            >
              Resolve Alert
            </Button>
          </>
        }
      >
        {openAlert && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              {[
                ['Merchant', openAlert.merchant],
                ['Amount', formatCurrency(openAlert.amount)],
                ['Risk Score', formatScore(openAlert.fraud_score)],
                ['Created', formatDate(openAlert.created_at)],
              ].map(([k, v]) => (
                <div key={k}>
                  <div className="text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-0.5">{k}</div>
                  <div className="font-semibold text-navy-700 dark:text-warm-200">{v}</div>
                </div>
              ))}
            </div>

            <div>
              <label className="block text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1.5">
                Resolution Notes
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Add resolution notes…"
                className="w-full px-3 py-2 text-xs font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none text-navy-700 dark:text-warm-200 placeholder:text-warm-400 resize-none"
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}