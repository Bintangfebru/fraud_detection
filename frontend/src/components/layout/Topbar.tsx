import { Sun, Moon, Bell, Wifi, WifiOff } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getHealth } from '@/api/analytics'
import { useThemeStore } from '@/stores/themeStore'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/utils/format'

interface TopbarProps {
  title: string
  breadcrumb?: string
}

export function Topbar({ title, breadcrumb }: TopbarProps) {
  const { theme, toggle } = useThemeStore()

  const { data: health } = useQuery({
    queryKey: queryKeys.health,
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: false,
  })

  const isHealthy = health?.status === 'ok'

  return (
    <header className="fixed top-0 left-0 right-0 h-[60px] z-30 flex items-center gap-4 px-5 glass-topbar">
      {/* Title */}
      <div className="flex-1 min-w-0">
        {breadcrumb && (
          <div className="text-[10px] font-mono uppercase tracking-widest text-stone-400 dark:text-white/30 leading-none mb-0.5">
            {breadcrumb}
          </div>
        )}
        <h1 className="font-display text-xl text-ink-800 dark:text-white leading-none tracking-tight">
          {title}
        </h1>
      </div>

      <div className="flex items-center gap-2">
        {/* Health badge */}
        <div
          className={cn(
            'hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-mono uppercase tracking-wider btn-glass',
            health == null ? 'text-stone-400' : isHealthy ? 'text-emerald-500' : 'text-coral-400',
          )}
        >
          {isHealthy ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
          {health == null ? 'connecting' : isHealthy ? 'operational' : 'degraded'}
        </div>

        {/* Theme toggle */}
        <button
          onClick={toggle}
          className="btn-glass p-2 text-stone-600 dark:text-white/50 hover:text-ink-800 dark:hover:text-white"
          title="Toggle theme"
        >
          {theme === 'light' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>

        {/* Notifications */}
        <button
          className="btn-glass p-2 text-stone-600 dark:text-white/50 hover:text-ink-800 dark:hover:text-white"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}