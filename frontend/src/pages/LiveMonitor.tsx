import { useState, useEffect, useRef, memo, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Wifi, WifiOff, Pause, Play, AlertTriangle } from 'lucide-react'
import { getTransactions } from '@/api/fraud'
import { getAnalyticsSummary } from '@/api/analytics'
import { queryKeys } from '@/lib/queryKeys'
import { Card, CardHeader } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatCurrency, formatDate, formatScore, cn } from '@/utils/format'

const REFRESH_INTERVAL = 5_000

// ── Memo: tiap baris tabel hanya re-render kalau tx atau isNew berubah ──
const LiveRow = memo(function LiveRow({ tx, isNew }: { tx: any; isNew: boolean }) {
  return (
    <tr
      className={cn(
        'border-b border-warm-200/60 dark:border-navy-700/50 transition-all duration-500',
        isNew ? 'bg-sage-50 dark:bg-sage-600/10' : 'hover:bg-warm-100 dark:hover:bg-navy-700/30',
        tx.status === 'FRAUD' && 'border-l-2 border-l-coral-400',
        tx.status === 'REVIEW' && 'border-l-2 border-l-amber-400',
      )}
    >
      <td className="px-4 py-2 font-semibold text-navy-700 dark:text-warm-200">
        {tx.reference}
        {isNew && <span className="ml-2 text-[9px] text-sage-400 uppercase tracking-wider">NEW</span>}
      </td>
      <td className="px-4 py-2 text-warm-600 dark:text-warm-400 max-w-[100px] truncate">{tx.merchant}</td>
      <td className="px-4 py-2 text-warm-500 dark:text-warm-400 uppercase">{tx.category.replace('_', ' ')}</td>
      <td className="px-4 py-2 text-navy-700 dark:text-warm-200">{formatCurrency(tx.amount, tx.currency)}</td>
      <td className="px-4 py-2">
        {tx.fraud_score != null ? (
          <span className={cn('font-bold', tx.fraud_score > 0.7 ? 'text-coral-400' : tx.fraud_score > 0.4 ? 'text-amber-400' : 'text-sage-400')}>
            {formatScore(tx.fraud_score)}
          </span>
        ) : <span className="text-warm-400">—</span>}
      </td>
      <td className="px-4 py-2 text-warm-500 dark:text-warm-400 whitespace-nowrap">{formatDate(tx.created_at)}</td>
      <td className="px-4 py-2"><StatusBadge status={tx.status} /></td>
    </tr>
  )
})

// ── Memo: review queue item ──
const ReviewItem = memo(function ReviewItem({ tx }: { tx: any }) {
  return (
    <div className="flex items-center justify-between p-3 bg-amber-50 dark:bg-amber-600/5 border border-amber-100 dark:border-amber-600/20 rounded-lg">
      <div className="flex items-center gap-4 text-xs font-mono">
        <span className="font-semibold text-navy-700 dark:text-warm-200">{tx.reference}</span>
        <span className="text-warm-500">{tx.merchant}</span>
        <span className="text-navy-700 dark:text-warm-200">{formatCurrency(tx.amount, tx.currency)}</span>
      </div>
      <div className="flex items-center gap-2">
        {tx.fraud_score != null && (
          <span className="text-xs font-mono text-amber-400 font-bold">{formatScore(tx.fraud_score)}</span>
        )}
        <StatusBadge status={tx.status} />
      </div>
    </div>
  )
})

export function LiveMonitor() {
  const [paused, setPaused] = useState(false)
  const [flashIds, setFlashIds] = useState<Set<string>>(new Set())
  const prevIdsRef = useRef<Set<string>>(new Set())

  const summary = useQuery({
    queryKey: queryKeys.analyticsSummary,
    queryFn: ({ signal }) => getAnalyticsSummary({ signal }),
    refetchInterval: paused ? false : REFRESH_INTERVAL,
  })

  const transactions = useQuery({
    queryKey: queryKeys.transactions({ page: 1, page_size: 50, sort: 'desc' }),
    queryFn: ({ signal }) => getTransactions({ page: 1, page_size: 50 }, { signal }),
    refetchInterval: paused ? false : REFRESH_INTERVAL,
    refetchIntervalInBackground: true,
  })

  useEffect(() => {
    if (!transactions.data) return
    const newIds = new Set(transactions.data.items.map((t) => t.id))
    const incoming = new Set([...newIds].filter((id) => !prevIdsRef.current.has(id)))
    if (incoming.size > 0) {
      setFlashIds(incoming)
      const timer = setTimeout(() => setFlashIds(new Set()), 2000)
      prevIdsRef.current = newIds
      return () => clearTimeout(timer)
    }
    prevIdsRef.current = newIds
  }, [transactions.data])

  // ── useMemo: filter fraud/review hanya kalau data berubah ──
  const { fraudItems, reviewItems } = useMemo(() => ({
    fraudItems: transactions.data?.items.filter((t) => t.status === 'FRAUD') ?? [],
    reviewItems: transactions.data?.items.filter((t) => t.status === 'REVIEW') ?? [],
  }), [transactions.data])

  const s = summary.data

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── Live Status Bar ── */}
      <Card className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider border',
            paused
              ? 'text-warm-400 border-warm-300 dark:border-navy-600'
              : 'text-sage-400 border-sage-50 dark:border-sage-600/20 bg-sage-50 dark:bg-sage-600/10',
          )}>
            {paused ? <WifiOff className="w-3 h-3" /> : <Wifi className="w-3 h-3" />}
            {paused ? 'Paused' : 'Live — updating every 5s'}
          </div>
          {transactions.isFetching && !paused && (
            <div className="w-1.5 h-1.5 rounded-full bg-sage-400 animate-pulse" />
          )}
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-4 text-xs font-mono">
            {s && (
              <>
                <span className="text-coral-400"><strong>{s.fraud_count}</strong> fraud</span>
                <span className="text-amber-400"><strong>{s.review_count}</strong> review</span>
                <span className="text-warm-500"><strong>{s.total_transactions}</strong> total</span>
              </>
            )}
          </div>
          <Button variant="outline" size="sm" onClick={() => setPaused((p) => !p)} icon={paused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}>
            {paused ? 'Resume' : 'Pause'}
          </Button>
        </div>
      </Card>

      {/* ── Alert Panel ── */}
      {fraudItems.length > 0 && (
        <Card className="border-coral-100 dark:border-coral-600/30 bg-coral-50/50 dark:bg-coral-600/5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-coral-400" />
            <span className="text-xs font-mono uppercase tracking-wider text-coral-400 font-semibold">
              {fraudItems.length} Active Fraud Alert{fraudItems.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {fraudItems.slice(0, 8).map((tx) => (
              <div key={tx.id} className="flex items-center gap-2 px-3 py-1.5 bg-warm-50 dark:bg-navy-800 border border-coral-100 dark:border-coral-600/20 rounded-lg text-xs font-mono">
                <span className="font-semibold text-navy-700 dark:text-warm-200">{tx.reference}</span>
                <span className="text-warm-500">{formatCurrency(tx.amount, tx.currency)}</span>
                {tx.fraud_score != null && <span className="text-coral-400 font-bold">{formatScore(tx.fraud_score)}</span>}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Live Feed Table ── */}
      <Card noPad>
        <div className="p-5 pb-0">
          <CardHeader
            title="Live Transaction Feed"
            subtitle={`Last 50 transactions · ${paused ? 'paused' : 'auto-refresh'}`}
            action={
              <div className="flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-coral-400 animate-pulse" />
                <span className="text-[10px] font-mono text-warm-500 dark:text-warm-400">LIVE</span>
              </div>
            }
          />
        </div>
        <div className="overflow-x-auto max-h-[60vh] overflow-y-auto scrollbar-thin">
          <table className="w-full text-xs font-mono">
            <thead className="sticky top-0 bg-warm-50 dark:bg-navy-800 z-10">
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['Reference', 'Merchant', 'Category', 'Amount', 'Score', 'Time', 'Status'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {transactions.data?.items.map((tx) => (
                <LiveRow key={tx.id} tx={tx} isNew={flashIds.has(tx.id)} />
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Review Queue ── */}
      {reviewItems.length > 0 && (
        <Card>
          <CardHeader title="Pending Review Queue" subtitle={`${reviewItems.length} transaction${reviewItems.length !== 1 ? 's' : ''} need review`} />
          <div className="space-y-2">
            {reviewItems.slice(0, 5).map((tx) => (
              <ReviewItem key={tx.id} tx={tx} />
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}