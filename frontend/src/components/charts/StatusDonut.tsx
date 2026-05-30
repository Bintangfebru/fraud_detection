import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from 'recharts'
import type { AnalyticsSummary, CategoryBreakdown } from '@/types/api'
import { useThemeStore } from '@/stores/themeStore'
import { formatNumber } from '@/utils/format'

// ── Status Donut ─────────────────────────────────────────────

const COLORS = ['#E07A5F', '#d4a050', '#81B29A']
const LABELS = ['Fraud', 'Review', 'Safe']

interface StatusDonutProps {
  summary: AnalyticsSummary
}

export function StatusDonut({ summary }: StatusDonutProps) {
  const data = [
    { name: 'Fraud', value: summary.fraud_count },
    { name: 'Review', value: summary.review_count },
    { name: 'Safe', value: summary.safe_count },
  ]

  const { theme } = useThemeStore()
  const isDark = theme === 'dark'

  return (
    <div className="flex flex-col items-center gap-4">
      <ResponsiveContainer width={160} height={160}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={48}
            outerRadius={72}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell key={index} fill={COLORS[index]} strokeWidth={0} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: isDark ? '#1e2035' : '#FDFCF7',
              border: `1px solid ${isDark ? '#2e314a' : '#ccc8b0'}`,
              borderRadius: 6,
              fontSize: 11,
              fontFamily: 'DM Mono',
            }}
          />
        </PieChart>
      </ResponsiveContainer>

      <div className="w-full space-y-1.5">
        {data.map((item, i) => (
          <div key={item.name} className="flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i] }} />
              <span className="text-warm-500 dark:text-warm-400">{LABELS[i]}</span>
            </div>
            <span className="font-semibold text-navy-700 dark:text-warm-200">
              {formatNumber(item.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Category Bar Chart ────────────────────────────────────────

interface CategoryBarProps {
  data: CategoryBreakdown[]
}

export function CategoryBar({ data }: CategoryBarProps) {
  const { theme } = useThemeStore()
  const isDark = theme === 'dark'
  const gridColor = isDark ? '#2e314a' : '#e0dcc8'
  const textColor = isDark ? '#9a9fc0' : '#81B29A'

  const chartData = data.slice(0, 10).map((d) => ({
    name: d.category.replace('_', ' '),
    Total: d.total,
    Fraud: d.fraud,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 9, fontFamily: 'DM Mono', fill: textColor }}
          axisLine={false}
          tickLine={false}
          interval={0}
          angle={-30}
          textAnchor="end"
          height={50}
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
        <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'DM Mono', paddingTop: 8 }} />
        <Bar dataKey="Total" fill={isDark ? '#3D405B' : '#CCC8B0'} radius={[2, 2, 0, 0]} />
        <Bar dataKey="Fraud" fill="#E07A5F" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
