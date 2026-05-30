import { cn } from '@/utils/format'
import type { InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  icon?: React.ReactNode
}

export function Input({ label, error, icon, className, ...props }: InputProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-[11px] font-mono uppercase tracking-wider text-stone-400 dark:text-white/35">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 dark:text-white/30 w-4 h-4">
            {icon}
          </div>
        )}
        <input
          {...props}
          className={cn(
            'glass-input w-full h-10 px-3 text-sm font-body text-ink-800 dark:text-white',
            'placeholder:text-stone-300 dark:placeholder:text-white/20',
            icon && 'pl-9',
            error && 'border-coral-400/50',
            className,
          )}
        />
      </div>
      {error && (
        <p className="text-xs font-mono text-coral-400">{error}</p>
      )}
    </div>
  )
}
