import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutGrid, Activity, Layers, BarChart2, FolderOpen,
  Users, Cpu, FileText, Settings, Shield, LogOut, MoreHorizontal,
} from 'lucide-react'
import { cn } from '@/utils/format'
import { useAuthStore } from '@/stores/authStore'
import { logout as apiLogout } from '@/api/auth'
import toast from 'react-hot-toast'
import { useState } from 'react'

interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  href: string
  permission: string
  badge?: 'fraud'
}

interface NavSection {
  section: string
  items: NavItem[]
}

const NAV: NavSection[] = [
  {
    section: 'Overview',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: <LayoutGrid className="w-5 h-5" />, href: '/dashboard', permission: 'view_dashboard' },
      { id: 'live', label: 'Live', icon: <Activity className="w-5 h-5" />, href: '/live', permission: 'view_live', badge: 'fraud' },
    ],
  },
  {
    section: 'Investigation',
    items: [
      { id: 'transactions', label: 'Transactions', icon: <Layers className="w-5 h-5" />, href: '/transactions', permission: 'view_transactions' },
      { id: 'analytics', label: 'Analytics', icon: <BarChart2 className="w-5 h-5" />, href: '/analytics', permission: 'view_analytics' },
      { id: 'cases', label: 'Cases', icon: <FolderOpen className="w-5 h-5" />, href: '/cases', permission: 'approve_review' },
    ],
  },
  {
    section: 'Administration',
    items: [
      { id: 'users', label: 'Users', icon: <Users className="w-5 h-5" />, href: '/users', permission: 'manage_users' },
      { id: 'models', label: 'Models', icon: <Cpu className="w-5 h-5" />, href: '/models', permission: 'manage_model' },
      { id: 'audit', label: 'Audit', icon: <FileText className="w-5 h-5" />, href: '/audit', permission: 'view_audit' },
      { id: 'settings', label: 'Settings', icon: <Settings className="w-5 h-5" />, href: '/settings', permission: 'view_dashboard' },
    ],
  },
]

// How many items to show directly in the bar before collapsing into "More"
const MAX_VISIBLE = 4

export function Sidebar() {
  const { user, can, logout, refreshToken } = useAuthStore()
  const navigate = useNavigate()
  const [moreOpen, setMoreOpen] = useState(false)

  const handleLogout = async () => {
    try { if (refreshToken) await apiLogout(refreshToken) } catch { /* ignore */ }
    logout()
    navigate('/login')
    toast.success('Logged out successfully')
  }

  // Flatten all permitted items
  const allItems = NAV.flatMap((s) => s.items).filter((item) => can(item.permission))
  const visibleItems = allItems.slice(0, MAX_VISIBLE)
  const overflowItems = allItems.slice(MAX_VISIBLE)

  return (
    <>
      {/* ── Floating bottom bar ───────────────────────────── */}
      <nav
        className={cn(
          'fixed bottom-5 left-1/2 -translate-x-1/2 z-50',
          'flex items-center gap-1 px-3 py-2',
          'rounded-[28px]',
          // Liquid glass — medium thickness
          'backdrop-blur-[24px]',
        )}
        style={{
          background: `
            radial-gradient(ellipse 60% 40% at 50% 10%, rgba(255,255,255,0.55) 0%, transparent 70%),
            linear-gradient(170deg, rgba(255,255,255,0.42) 0%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.28) 100%)
          `,
          borderTop: '1.5px solid rgba(255,255,255,0.85)',
          borderLeft: '1.5px solid rgba(255,255,255,0.70)',
          borderRight: '1px solid rgba(255,255,255,0.30)',
          borderBottom: '1px solid rgba(255,255,255,0.25)',
          boxShadow: `
            inset 0 2px 0 rgba(255,255,255,0.70),
            inset 0 -1px 0 rgba(0,0,0,0.06),
            inset 2px 0 0 rgba(255,255,255,0.22),
            0 8px 32px rgba(0,0,0,0.16),
            0 2px 8px rgba(0,0,0,0.10)
          `,
          backdropFilter: 'blur(24px) saturate(1.6) brightness(1.06)',
          WebkitBackdropFilter: 'blur(24px) saturate(1.6) brightness(1.06)',
        }}
      >
        {/* Logo pill */}
        <div
          className="flex items-center justify-center w-9 h-9 rounded-2xl flex-shrink-0 mr-1"
          style={{ background: 'var(--color-ink-700, #2d3048)' }}
        >
          <Shield className="w-4 h-4 text-white" />
        </div>

        {/* Thin separator */}
        <div className="w-px h-6 mx-1 rounded-full" style={{ background: 'rgba(0,0,0,0.10)' }} />

        {/* Nav items */}
        {visibleItems.map((item) => (
          <NavLink
            key={item.id}
            to={item.href}
            className={({ isActive }) =>
              cn(
                'relative flex flex-col items-center justify-center gap-0.5',
                'w-14 h-12 rounded-2xl text-[10px] font-medium tracking-wide transition-all duration-150',
                isActive
                  ? 'nav-active text-ink-800 dark:text-white'
                  : 'text-stone-500 dark:text-white/40 hover:text-ink-800 dark:hover:text-white/80 hover:bg-white/40 dark:hover:bg-white/06',
              )
            }
          >
            {({ isActive }) => (
              <>
                <span className={cn(isActive && 'scale-110 transition-transform duration-150')}>
                  {item.icon}
                </span>
                <span className="truncate max-w-full px-1">{item.label}</span>
                {item.badge && (
                  <span className="absolute top-2 right-2.5 w-1.5 h-1.5 rounded-full bg-[#E07A5F] animate-pulse" />
                )}
              </>
            )}
          </NavLink>
        ))}

        {/* More button */}
        {overflowItems.length > 0 && (
          <button
            onClick={() => setMoreOpen((v) => !v)}
            className={cn(
              'relative flex flex-col items-center justify-center gap-0.5',
              'w-14 h-12 rounded-2xl text-[10px] font-medium tracking-wide transition-all duration-150',
              moreOpen
                ? 'nav-active text-ink-800 dark:text-white'
                : 'text-stone-500 dark:text-white/40 hover:text-ink-800 hover:bg-white/40',
            )}
          >
            <MoreHorizontal className="w-5 h-5" />
            <span>More</span>
          </button>
        )}

        {/* Thin separator */}
        <div className="w-px h-6 mx-1 rounded-full" style={{ background: 'rgba(0,0,0,0.10)' }} />

        {/* User avatar + logout */}
        <div className="flex items-center gap-1.5 pl-1">
          <div
            className="w-9 h-9 rounded-2xl flex items-center justify-center flex-shrink-0 text-sm font-semibold uppercase select-none"
            style={{
              background: 'rgba(255,255,255,0.55)',
              border: '1px solid rgba(255,255,255,0.70)',
              color: '#2d3048',
            }}
            title={user?.username}
          >
            {user?.username?.charAt(0) ?? '?'}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center justify-center w-8 h-8 rounded-xl transition-all text-stone-400 hover:text-[#E07A5F] hover:bg-white/40"
            title="Logout"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </nav>

      {/* ── Overflow tray (floats above the bar) ─────────── */}
      {moreOpen && overflowItems.length > 0 && (
        <>
          {/* Backdrop tap-to-close */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setMoreOpen(false)}
          />

          <div
            className="fixed bottom-[84px] left-1/2 -translate-x-1/2 z-50 flex items-center gap-1 px-3 py-2 rounded-[24px]"
            style={{
              background: `
                radial-gradient(ellipse 60% 40% at 50% 10%, rgba(255,255,255,0.55) 0%, transparent 70%),
                linear-gradient(170deg, rgba(255,255,255,0.42) 0%, rgba(255,255,255,0.12) 50%, rgba(255,255,255,0.28) 100%)
              `,
              borderTop: '1.5px solid rgba(255,255,255,0.85)',
              borderLeft: '1.5px solid rgba(255,255,255,0.70)',
              borderRight: '1px solid rgba(255,255,255,0.30)',
              borderBottom: '1px solid rgba(255,255,255,0.25)',
              boxShadow: `
                inset 0 2px 0 rgba(255,255,255,0.70),
                inset 0 -1px 0 rgba(0,0,0,0.06),
                0 8px 32px rgba(0,0,0,0.16),
                0 2px 8px rgba(0,0,0,0.10)
              `,
              backdropFilter: 'blur(24px) saturate(1.6) brightness(1.06)',
              WebkitBackdropFilter: 'blur(24px) saturate(1.6) brightness(1.06)',
              animation: 'slideUp 0.18s cubic-bezier(0.34,1.56,0.64,1)',
            }}
          >
            {overflowItems.map((item) => (
              <NavLink
                key={item.id}
                to={item.href}
                onClick={() => setMoreOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'relative flex flex-col items-center justify-center gap-0.5',
                    'w-14 h-12 rounded-2xl text-[10px] font-medium tracking-wide transition-all duration-150',
                    isActive
                      ? 'nav-active text-ink-800 dark:text-white'
                      : 'text-stone-500 dark:text-white/40 hover:text-ink-800 hover:bg-white/40',
                  )
                }
              >
                {item.icon}
                <span className="truncate max-w-full px-1">{item.label}</span>
              </NavLink>
            ))}
          </div>
        </>
      )}
    </>
  )
}