import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, Role } from '@/types/api'

// ── Permissions map ───────────────────────────────────────────
const PERMISSIONS: Record<Role, string[]> = {
  admin: [
    'view_dashboard', 'view_transactions', 'view_analytics', 'view_audit',
    'manage_users', 'manage_model', 'manage_config', 'approve_review',
    'view_all_transactions', 'submit_transaction', 'export_data', 'view_live',
  ],
  analyst: [
    'view_dashboard', 'view_transactions', 'view_analytics', 'view_audit',
    'approve_review', 'view_all_transactions', 'submit_transaction', 'export_data', 'view_live',
  ],
  auditor: [
    'view_dashboard', 'view_transactions', 'view_analytics', 'view_audit', 'export_data',
  ],
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean

  setAuth: (user: User, accessToken: string, refreshToken: string) => void
  setUser: (user: User) => void
  logout: () => void
  can: (permission: string) => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setAuth: (user, accessToken, refreshToken) =>
        set({ user, accessToken, refreshToken, isAuthenticated: true }),

      setUser: (user) => set({ user }),

      logout: () =>
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false }),

      can: (permission) => {
        const role = get().user?.role
        if (!role) return false
        return (PERMISSIONS[role] ?? []).includes(permission)
      },
    }),
    {
      name: 'fraudshield-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
)
