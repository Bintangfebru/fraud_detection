import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/utils/format'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  footer?: React.ReactNode
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
}

const SIZES = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
}

export function Modal({ open, onClose, title, subtitle, footer, children, size = 'md' }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-ink-900/30 backdrop-blur-sm"
        onClick={onClose}
      />
      {/* Panel */}
      <div
        className={cn(
          'relative w-full glass-card p-6 animate-slide-up',
          SIZES[size],
        )}
      >
        {title && (
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="font-display text-xl text-ink-800 dark:text-white">{title}</h2>
              {subtitle && (
                <p className="text-sm text-stone-400 dark:text-white/40 mt-0.5">{subtitle}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="btn-glass p-1.5 text-stone-400 hover:text-ink-800 dark:hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
        {children}
        {footer && (
          <div className="flex justify-end gap-2 mt-5">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}