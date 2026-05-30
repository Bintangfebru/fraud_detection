import { cn } from '@/utils/format'

interface CardProps {
  children: React.ReactNode
  className?: string
  noPad?: boolean
}

export function Card({ children, className, noPad }: CardProps) {
  return (
    <div className={cn('glass-card', !noPad && 'p-5', className)}>
      {children}
    </div>
  )
}

interface CardHeaderProps {
  title: string
  subtitle?: string
  action?: React.ReactNode
  className?: string
}

export function CardHeader({ title, subtitle, action, className }: CardHeaderProps) {
  return (
    <div className={cn('flex items-start justify-between gap-4 mb-4', className)}>
      <div>
        <h3 className="font-display text-lg text-ink-800 dark:text-white leading-tight tracking-tight">
          {title}
        </h3>
        {subtitle && (
          <p className="text-xs text-stone-400 dark:text-white/35 mt-0.5 font-mono">{subtitle}</p>
        )}
      </div>
      {action && <div className="flex-shrink-0">{action}</div>}
    </div>
  )
}

export function StatCard({
  label,
  value,
  delta,
  deltaLabel,
  icon,
  variant = 'default',
  loading,
}: {
  label: string
  value: string | number
  delta?: string
  deltaLabel?: string
  icon?: React.ReactNode
  variant?: 'default' | 'fraud' | 'review' | 'safe' | 'info'
  loading?: boolean
}) {
  const accentMap = {
    default: 'text-ink-800 dark:text-white/80',
    fraud:   'text-coral-400',
    review:  'text-amber-400',
    safe:    'text-emerald-500',
    info:    'text-ink-700 dark:text-white/70',
  }
  const iconBgMap = {
    default: 'bg-stone-100/70 dark:bg-white/06',
    fraud:   'bg-coral-400/10',
    review:  'bg-amber-400/10',
    safe:    'bg-emerald-400/10',
    info:    'bg-ink-700/08 dark:bg-white/06',
  }
  const deltaColorMap = {
    default: 'text-stone-500 dark:text-white/40',
    fraud:   'text-coral-400/80',
    review:  'text-amber-500/80',
    safe:    'text-emerald-500/80',
    info:    'text-stone-500 dark:text-white/40',
  }

  return (
    <div className="glass-stat p-5 flex flex-col gap-4">
      {/* Top row: icon + label side by side */}
      <div className="flex items-center gap-2.5">
        {icon && (
          <div className={cn(
            'w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0',
            iconBgMap[variant],
          )}>
            <span className={cn('flex items-center justify-center w-4 h-4', accentMap[variant])}>
              {icon}
            </span>
          </div>
        )}
        <span className="text-[10px] font-mono uppercase tracking-widest text-stone-400 dark:text-white/35 leading-tight">
          {label}
        </span>
      </div>

      {/* Value */}
      {loading ? (
        <div className="skeleton h-9 w-28" />
      ) : (
        <div className={cn('font-display text-4xl leading-none', accentMap[variant])}>
          {value}
        </div>
      )}

      {/* Delta */}
      {(delta || deltaLabel) && (
        <div className="flex items-center gap-1.5 text-xs font-mono">
          {delta && (
            <span className={cn('font-medium', deltaColorMap[variant])}>{delta}</span>
          )}
          {deltaLabel && (
            <span className="text-stone-400 dark:text-white/30">{deltaLabel}</span>
          )}
        </div>
      )}
    </div>
  )
}