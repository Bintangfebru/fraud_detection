import { useState, memo, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAnalyticsSummary, getFraudRateTrend, getCategoryBreakdown, getTopMerchants } from '@/api/analytics'
import { queryKeys } from '@/lib/queryKeys'
import { Card, CardHeader } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { ChartSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { FraudTrendChart } from '@/components/charts/FraudTrendChart'
import { CategoryBar } from '@/components/charts/StatusDonut'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, RadarChart,
  Radar, PolarGrid, PolarAngleAxis,
} from 'recharts'
import { formatPercent, formatCurrency, formatNumber } from '@/utils/format'
import { useThemeStore } from '@/stores/themeStore'

type Range = '24h' | '7d' | '30d'

// ── Memo: KPI card ──
const KpiCard = memo(function KpiCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <Card className="p-4">
      <div className="text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-1">{label}</div>
      <div className={`font-display font-bold text-2xl ${accent ?? 'text-navy-700 dark:text-warm-200'}`}>{value}</div>
    </Card>
  )
})

// ── Memo: Merchant table row ──
const MerchantRow = memo(function MerchantRow({ m, i, formatNumber, formatPercent }: any) {
  return (
    <tr className="border-b border-warm-200/60 dark:border-navy-700/50 hover:bg-warm-100 dark:hover:bg-navy-700/30 transition-colors">
      <td className="px-4 py-2.5 text-warm-400 dark:text-warm-500">{i + 1}</td>
      <td className="px-4 py-2.5 font-semibold text-navy-700 dark:text-warm-200">{m.merchant}</td>
      <td className="px-4 py-2.5 text-warm-600 dark:text-warm-400">{formatNumber(m.total)}</td>
      <td className="px-4 py-2.5 text-coral-400">{formatNumber(m.fraud)}</td>
      <td className="px-4 py-2.5">
        <div className="flex items-center gap-2">
          <div className="w-20 h-1.5 bg-warm-300 dark:bg-navy-700 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(m.fraud_rate * 100, 100)}%`,
                background: m.fraud_rate > 0.3 ? '#E07A5F' : m.fraud_rate > 0.1 ? '#d4a050' : '#81B29A',
              }}
            />
          </div>
          <span className={m.fraud_rate > 0.3 ? 'text-coral-400' : 'text-warm-600 dark:text-warm-400'}>
            {formatPercent(m.fraud_rate)}
          </span>
        </div>
      </td>
    </tr>
  )
})

export function Analytics() {
  const [range, setRange] = useState<Range>('7d')
  const { theme } = useThemeStore()
  const isDark = theme === 'dark'

  // ── useMemo: chart style objects agar tidak dibuat ulang tiap render ──
  const chartStyles = useMemo(() => ({
    gridColor: isDark ? '#2e314a' : '#e0dcc8',
    textColor: isDark ? '#9a9fc0' : '#81B29A',
    tooltipStyle: {
      background: isDark ? '#1e2035' : '#FDFCF7',
      border: `1px solid ${isDark ? '#2e314a' : '#ccc8b0'}`,
      borderRadius: 6,
      fontSize: 11,
      fontFamily: 'DM Mono',
    },
  }), [isDark])

  const summary    = useQuery({ queryKey: queryKeys.analyticsSummary, queryFn: ({ signal }) => getAnalyticsSummary({ signal }) })
  const trend      = useQuery({ queryKey: queryKeys.fraudTrend(range), queryFn: ({ signal }) => getFraudRateTrend(range, { signal }) })
  const categories = useQuery({ queryKey: queryKeys.categoryBreakdown, queryFn: ({ signal }) => getCategoryBreakdown({ signal }) })
  const merchants  = useQuery({ queryKey: queryKeys.topMerchants(10), queryFn: ({ signal }) => getTopMerchants(10, { signal }) })

  // ── useMemo: transform data chart hanya kalau data berubah ──
  const merchantChartData = useMemo(() =>
    merchants.data?.map((m) => ({
      name: m.merchant.length > 12 ? m.merchant.slice(0, 12) + '…' : m.merchant,
      Total: m.total,
      Fraud: m.fraud,
      'Rate %': +(m.fraud_rate * 100).toFixed(1),
    })),
    [merchants.data]
  )

  const radarData = useMemo(() =>
    categories.data?.slice(0, 6).map((c) => ({
      category: c.category.replace('_', ' '),
      'Fraud Rate': +(c.fraud_rate * 100).toFixed(1),
    })),
    [categories.data]
  )

  const s = summary.data

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── KPI Summary Row ── */}
      {summary.isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-7 w-28" />
            </div>
          ))}
        </div>
      ) : s ? (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
          <KpiCard label="Total Transactions" value={formatNumber(s.total_transactions)} />
          <KpiCard label="Fraud Detected" value={formatNumber(s.fraud_count)} accent="text-coral-400" />
          <KpiCard label="Under Review" value={formatNumber(s.review_count)} accent="text-amber-400" />
          <KpiCard label="Fraud Rate" value={formatPercent(s.fraud_rate)} accent="text-coral-400" />
          <KpiCard label="Fraud Amount" value={formatCurrency(s.fraud_amount)} accent="text-coral-400" />
        </div>
      ) : null}

      {/* ── Trend Chart ── */}
      <Card>
        <CardHeader
          title="Fraud Trend Over Time"
          subtitle={`Showing data for last ${range}`}
          action={
            <div className="flex gap-1">
              {(['24h', '7d', '30d'] as Range[]).map((r) => (
                <button
                  key={r}
                  onClick={() => setRange(r)}
                  className={`px-2.5 py-1 text-[10px] font-mono uppercase rounded transition-colors ${
                    range === r
                      ? 'bg-navy-700 text-warm-100 dark:bg-coral-400 dark:text-white'
                      : 'text-warm-500 hover:text-navy-700 dark:hover:text-warm-200'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          }
        />
        {trend.isLoading ? (
          <ChartSkeleton height={240} />
        ) : trend.isError ? (
          <ErrorState compact message="Failed to load trend" onRetry={() => trend.refetch()} />
        ) : trend.data ? (
          <FraudTrendChart data={trend.data} />
        ) : null}
      </Card>

      {/* ── Merchant Volume + Radar ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader title="Top Merchants by Fraud" subtitle="Fraud count vs total volume" />
          {merchants.isLoading ? (
            <ChartSkeleton height={260} />
          ) : merchants.isError ? (
            <ErrorState compact message="Failed to load merchants" onRetry={() => merchants.refetch()} />
          ) : merchantChartData ? (
            <ResponsiveContainer width="100%" height={260}>
              <ComposedChart data={merchantChartData} margin={{ top: 4, right: 8, left: -20, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartStyles.gridColor} vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 9, fontFamily: 'DM Mono', fill: chartStyles.textColor }} axisLine={false} tickLine={false} angle={-30} textAnchor="end" height={50} />
                <YAxis yAxisId="left" tick={{ fontSize: 10, fontFamily: 'DM Mono', fill: chartStyles.textColor }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fontFamily: 'DM Mono', fill: chartStyles.textColor }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip contentStyle={chartStyles.tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'DM Mono', paddingTop: 8 }} />
                <Bar yAxisId="left" dataKey="Total" fill={isDark ? '#3D405B' : '#CCC8B0'} radius={[2, 2, 0, 0]} />
                <Bar yAxisId="left" dataKey="Fraud" fill="#E07A5F" radius={[2, 2, 0, 0]} />
                <Line yAxisId="right" type="monotone" dataKey="Rate %" stroke="#d4a050" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : null}
        </Card>

        <Card>
          <CardHeader title="Fraud Rate by Category" subtitle="Radar view" />
          {categories.isLoading ? (
            <ChartSkeleton height={260} />
          ) : radarData ? (
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid stroke={chartStyles.gridColor} />
                <PolarAngleAxis dataKey="category" tick={{ fontSize: 9, fontFamily: 'DM Mono', fill: chartStyles.textColor }} />
                <Radar dataKey="Fraud Rate" stroke="#E07A5F" fill="#E07A5F" fillOpacity={0.25} strokeWidth={2} />
                <Tooltip contentStyle={chartStyles.tooltipStyle} formatter={(v) => [`${v}%`, 'Fraud Rate']} />
              </RadarChart>
            </ResponsiveContainer>
          ) : null}
        </Card>
      </div>

      {/* ── Category Bar ── */}
      <Card>
        <CardHeader title="Fraud Volume by Category" subtitle="Top 10 categories" />
        {categories.isLoading ? (
          <ChartSkeleton height={220} />
        ) : categories.isError ? (
          <ErrorState compact message="Failed to load categories" onRetry={() => categories.refetch()} />
        ) : categories.data ? (
          <CategoryBar data={categories.data} />
        ) : null}
      </Card>

      {/* ── Top Merchants Table ── */}
      <Card noPad>
        <div className="p-5 pb-0">
          <CardHeader title="Top Merchants — Fraud Detail" subtitle="Ranked by fraud count" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['#', 'Merchant', 'Total Tx', 'Fraud Tx', 'Fraud Rate'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {merchants.isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-warm-200/60 dark:border-navy-700/50">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-4 py-2.5"><Skeleton className="h-4 w-20" /></td>
                    ))}
                  </tr>
                ))
              ) : (
                merchants.data?.map((m, i) => (
                  <MerchantRow key={m.merchant} m={m} i={i} formatNumber={formatNumber} formatPercent={formatPercent} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}