import { cn } from '@/utils/format'
import type { FraudStatus } from '@/types/api'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'fraud' | 'review' | 'safe' | 'info' | 'neutral' | 'success'
  size?: 'sm' | 'md'
  className?: string
  dot?: boolean
}

const VARIANTS = {
  fraud:   'badge-fraud',
  review:  'badge-review',
  safe:    'badge-safe',
  info:    'bg-sky-400/12 text-sky-500 border border-sky-400/20',
  neutral: 'badge-neutral',
  success: 'badge-safe',
}

const DOT_COLORS = {
  fraud:   'bg-coral-400',
  review:  'bg-amber-400',
  safe:    'bg-emerald-500',
  info:    'bg-sky-400',
  neutral: 'bg-stone-400',
  success: 'bg-emerald-500',
}

export function Badge({ children, variant = 'neutral', size = 'md', className, dot }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-mono rounded-lg font-medium uppercase tracking-wide',
        size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-[10px] px-2.5 py-1',
        VARIANTS[variant],
        className,
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', DOT_COLORS[variant])} />}
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: FraudStatus }) {
  const map: Record<FraudStatus, { variant: BadgeProps['variant']; label: string }> = {
    FRAUD:  { variant: 'fraud',  label: 'Fraud' },
    REVIEW: { variant: 'review', label: 'Review' },
    SAFE:   { variant: 'safe',   label: 'Safe' },
  }
  const { variant, label } = map[status]
  return <Badge variant={variant} dot>{label}</Badge>
}
