import { useState, memo, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Activity, AlertTriangle, ShieldCheck, TrendingUp,
  ArrowRight, RefreshCw,
} from 'lucide-react'

import { getAnalyticsSummary, getFraudRateTrend, getCategoryBreakdown } from '@/api/analytics'
import { getTransactions } from '@/api/fraud'
import { queryKeys } from '@/lib/queryKeys'
import { Card, CardHeader, StatCard } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { StatCardSkeleton, ChartSkeleton, TableRowSkeleton } from '@/components/ui/Skeleton'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { FraudTrendChart } from '@/components/charts/FraudTrendChart'
import { StatusDonut, CategoryBar } from '@/components/charts/StatusDonut'
import { formatCurrency, formatNumber, formatPercent, formatDate } from '@/utils/format'

type TrendRange = '24h' | '7d' | '30d'

// ── Memo: StatCards agar tidak re-render saat trendRange berubah ──
const StatCards = memo(function StatCards({ s, isLoading, isError, onRetry }: {
  s: any
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}) {
  if (isLoading) return <>{Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}</>
  if (isError) return <div className="col-span-4"><ErrorState compact message="Failed to load summary" onRetry={onRetry} /></div>
  if (!s) return null
  return (
    <>
      <StatCard label="Total Transactions" value={formatNumber(s.total_transactions)} icon={<Activity />} variant="info" delta={formatNumber(s.total_transactions)} deltaLabel="all time" />
      <StatCard label="Fraud Detected" value={formatNumber(s.fraud_count)} icon={<AlertTriangle />} variant="fraud" delta={formatPercent(s.fraud_rate)} deltaLabel="fraud rate" />
      <StatCard label="Pending Review" value={formatNumber(s.review_count)} icon={<TrendingUp />} variant="review" delta={String(s.open_alerts)} deltaLabel="open alerts" />
      <StatCard label="Protected Volume" value={formatCurrency(s.fraud_amount)} icon={<ShieldCheck />} variant="safe" delta={formatCurrency(s.total_amount)} deltaLabel="total volume" />
    </>
  )
})

// ── Memo: TrendRangeButtons ──
const TrendRangeButtons = memo(function TrendRangeButtons({ trendRange, onChange }: {
  trendRange: TrendRange
  onChange: (r: TrendRange) => void
}) {
  return (
    <div className="flex gap-1 p-1 glass-card rounded-xl">
      {(['24h', '7d', '30d'] as TrendRange[]).map((r) => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={`px-2.5 py-1 text-[10px] font-mono uppercase rounded-lg transition-all ${
            trendRange === r
              ? 'bg-ink-700 dark:bg-coral-400 text-white shadow-sm'
              : 'text-stone-400 hover:text-ink-800 dark:hover:text-white/70'
          }`}
        >
          {r}
        </button>
      ))}
    </div>
  )
})

// ── Memo: RecentTxRow agar tiap baris tidak re-render semua ──
const RecentTxRow = memo(function RecentTxRow({ tx }: { tx: any }) {
  return (
    <tr className="border-b border-white/30 dark:border-white/04 hover:bg-white/30 dark:hover:bg-white/03 transition-colors">
      <td className="px-5 py-3 text-ink-800 dark:text-white/70 font-mono font-medium truncate max-w-[100px]">{tx.reference}</td>
      <td className="px-5 py-3 text-stone-500 dark:text-white/40 truncate max-w-[120px] font-body">{tx.merchant}</td>
      <td className="px-5 py-3 text-ink-800 dark:text-white/70 font-mono">{formatCurrency(tx.amount, tx.currency)}</td>
      <td className="px-5 py-3 text-stone-400 dark:text-white/30 font-mono">{formatDate(tx.created_at)}</td>
      <td className="px-5 py-3"><StatusBadge status={tx.status} /></td>
    </tr>
  )
})

export function Dashboard() {
  const [trendRange, setTrendRange] = useState<TrendRange>('7d')

  const summary    = useQuery({ queryKey: queryKeys.analyticsSummary, queryFn: ({ signal }) => getAnalyticsSummary({ signal }), refetchInterval: 60_000 })
  const trend      = useQuery({ queryKey: queryKeys.fraudTrend(trendRange), queryFn: ({ signal }) => getFraudRateTrend(trendRange, { signal }) })
  const categories = useQuery({ queryKey: queryKeys.categoryBreakdown, queryFn: ({ signal }) => getCategoryBreakdown({ signal }) })
  const recentTx   = useQuery({ queryKey: queryKeys.transactions({ page: 1, page_size: 10 }), queryFn: ({ signal }) => getTransactions({ page: 1, page_size: 10 }, { signal }), refetchInterval: 30_000 })

  const s = summary.data

  // ── useMemo: hitung data donut hanya kalau s berubah ──
  const donutData = useMemo(() => s ?? null, [s])

  return (
    <div className="space-y-5 animate-fade-in">
      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCards
          s={s}
          isLoading={summary.isLoading}
          isError={summary.isError}
          onRetry={() => summary.refetch()}
        />
      </div>

      {/* ── Trend + Donut ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Transaction Volume & Fraud Rate"
            subtitle={`Last ${trendRange} · live data`}
            action={<TrendRangeButtons trendRange={trendRange} onChange={setTrendRange} />}
          />
          {trend.isLoading ? (
            <ChartSkeleton height={220} />
          ) : trend.isError ? (
            <ErrorState compact message="Failed to load trend" onRetry={() => trend.refetch()} />
          ) : trend.data ? (
            <FraudTrendChart data={trend.data} />
          ) : null}
        </Card>

        <Card>
          <CardHeader title="Status Distribution" subtitle="All time" />
          {summary.isLoading ? (
            <ChartSkeleton height={220} />
          ) : donutData ? (
            <StatusDonut summary={donutData} />
          ) : null}
        </Card>
      </div>

      {/* ── Category + Recent Tx ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader title="Fraud by Category" subtitle="Top 10 categories" />
          {categories.isLoading ? (
            <ChartSkeleton height={220} />
          ) : categories.isError ? (
            <ErrorState compact message="Failed to load categories" onRetry={() => categories.refetch()} />
          ) : categories.data ? (
            <CategoryBar data={categories.data} />
          ) : null}
        </Card>

        <Card className="lg:col-span-2" noPad>
          <div className="p-5 pb-0">
            <CardHeader
              title="Recent Transactions"
              subtitle="Last 10 · auto-refresh"
              action={
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => recentTx.refetch()} icon={<RefreshCw className={`w-3.5 h-3.5 ${recentTx.isFetching ? 'animate-spin' : ''}`} />}>
                    Refresh
                  </Button>
                  <Link to="/transactions">
                    <Button variant="outline" size="sm" icon={<ArrowRight className="w-3.5 h-3.5" />}>View All</Button>
                  </Link>
                </div>
              }
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-white/40 dark:border-white/06">
                  {['Reference', 'Merchant', 'Amount', 'Date', 'Status'].map((h) => (
                    <th key={h} className="px-5 py-3 text-left text-[10px] uppercase tracking-wider text-stone-400 dark:text-white/30 font-mono">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recentTx.isLoading ? (
                  Array.from({ length: 6 }).map((_, i) => <TableRowSkeleton key={i} cols={5} />)
                ) : recentTx.isError ? (
                  <tr><td colSpan={5} className="px-5 py-8"><ErrorState compact message="Failed to load transactions" onRetry={() => recentTx.refetch()} /></td></tr>
                ) : (
                  recentTx.data?.items.map((tx) => (
                    <RecentTxRow key={tx.id} tx={tx} />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}