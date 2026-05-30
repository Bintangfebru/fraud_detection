import { AlertTriangle, RefreshCw } from 'lucide-react'
import { cn } from '@/utils/format'

interface ErrorStateProps {
  message?: string
  onRetry?: () => void
  compact?: boolean
}

export function ErrorState({ message = 'Something went wrong', onRetry, compact }: ErrorStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center text-center gap-3', compact ? 'py-6' : 'py-16')}>
      <div className="w-12 h-12 rounded-2xl bg-coral-400/10 flex items-center justify-center">
        <AlertTriangle className="w-5 h-5 text-coral-400" />
      </div>
      <div>
        <p className="font-display text-base text-ink-800 dark:text-white/70">Something went wrong</p>
        <p className="text-xs font-mono text-stone-400 dark:text-white/30 mt-0.5">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn-glass flex items-center gap-1.5 h-8 px-3 text-xs text-stone-600 dark:text-white/50"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try again
        </button>
      )}
    </div>
  )
}

interface EmptyStateProps {
  title?: string
  description?: string
  action?: React.ReactNode
  icon?: React.ReactNode   // ✅ ditambahkan
}

export function EmptyState({ title = 'No data found', description, action, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-3 py-16">
      <div className="w-12 h-12 rounded-2xl bg-stone-100/80 dark:bg-white/06 flex items-center justify-center">
        {icon ? (                                                          // ✅ ditambahkan
          <span className="text-stone-400 dark:text-white/30">{icon}</span>
        ) : (
          <span className="text-2xl">🗂</span>
        )}
      </div>
      <div>
        <p className="font-display text-base text-ink-800 dark:text-white/70">{title}</p>
        {description && <p className="text-xs font-mono text-stone-400 dark:text-white/30 mt-0.5">{description}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}