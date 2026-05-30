import { cn } from '@/utils/format'
import { Loader2 } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
}

const VARIANTS = {
  primary:   'btn-primary text-white font-medium',
  secondary: 'btn-glass text-stone-700 dark:text-white/70 font-medium',
  ghost:     'bg-transparent text-stone-600 dark:text-white/50 hover:bg-white/30 dark:hover:bg-white/06 border border-transparent rounded-xl transition-all',
  danger:    'bg-coral-400 text-white hover:bg-coral-500 border-transparent rounded-xl shadow-md transition-all',
  outline:   'btn-glass text-stone-700 dark:text-white/60 font-medium',
}

const SIZES = {
  sm: 'h-7 px-3 text-xs gap-1.5',
  md: 'h-9 px-4 text-sm gap-2',
  lg: 'h-11 px-6 text-base gap-2.5',
}

export function Button({
  children, variant = 'secondary', size = 'md', loading, icon,
  disabled, className, ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-body transition-all duration-150',
        'focus:outline-none focus:ring-2 focus:ring-ink-700/20 dark:focus:ring-white/12',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
    >
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  )
}
