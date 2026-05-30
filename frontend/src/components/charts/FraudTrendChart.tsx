import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import type { FraudRateTrend } from '@/types/api'
import { useThemeStore } from '@/stores/themeStore'

interface FraudTrendChartProps {
  data: FraudRateTrend
}

export function FraudTrendChart({ data }: FraudTrendChartProps) {
  const { theme } = useThemeStore()
  const isDark = theme === 'dark'

  const chartData = data.labels.map((label, i) => ({
    label,
    Safe: data.safe_counts[i] ?? 0,
    Review: data.review_counts[i] ?? 0,
    Fraud: data.fraud_counts[i] ?? 0,
    rate: data.fraud_rates[i] != null ? +(data.fraud_rates[i]! * 100).toFixed(2) : 0,
  }))

  const gridColor = isDark ? '#2e314a' : '#e0dcc8'
  const textColor = isDark ? '#9a9fc0' : '#81B29A'

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="gradSafe" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#81B29A" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#81B29A" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradReview" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#d4a050" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#d4a050" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gradFraud" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#E07A5F" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#E07A5F" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fontFamily: 'DM Mono', fill: textColor }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 10, fontFamily: 'DM Mono', fill: textColor }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            background: isDark ? '#1e2035' : '#FDFCF7',
            border: `1px solid ${isDark ? '#2e314a' : '#ccc8b0'}`,
            borderRadius: 6,
            fontSize: 11,
            fontFamily: 'DM Mono',
          }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, fontFamily: 'DM Mono', paddingTop: 8 }}
        />
        <Area type="monotone" dataKey="Safe" stroke="#81B29A" fill="url(#gradSafe)" strokeWidth={2} dot={false} />
        <Area type="monotone" dataKey="Review" stroke="#d4a050" fill="url(#gradReview)" strokeWidth={2} dot={false} />
        <Area type="monotone" dataKey="Fraud" stroke="#E07A5F" fill="url(#gradFraud)" strokeWidth={2} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}
