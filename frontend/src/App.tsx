import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useEffect, lazy, Suspense } from 'react'
import { ReactLenis } from 'lenis/react'

import { useAuthStore } from '@/stores/authStore'
import { useThemeStore } from '@/stores/themeStore'
import { AppLayout } from '@/components/layout/AppLayout'

// ── Lazy load semua halaman (hanya load saat dibuka) ──────────
const Login        = lazy(() => import('@/pages/Login').then(m => ({ default: m.Login })))
const Dashboard    = lazy(() => import('@/pages/Dashboard').then(m => ({ default: m.Dashboard })))
const Transactions = lazy(() => import('@/pages/Transactions').then(m => ({ default: m.Transactions })))
const Analytics    = lazy(() => import('@/pages/Analytics').then(m => ({ default: m.Analytics })))
const LiveMonitor  = lazy(() => import('@/pages/LiveMonitor').then(m => ({ default: m.LiveMonitor })))
const Cases        = lazy(() => import('@/pages/Cases').then(m => ({ default: m.Cases })))
const Users        = lazy(() => import('@/pages/Users').then(m => ({ default: m.Users })))
const Models       = lazy(() => import('@/pages/Models').then(m => ({ default: m.Models })))
const Audit        = lazy(() => import('@/pages/Audit').then(m => ({ default: m.Audit })))
const Settings     = lazy(() => import('@/pages/Settings').then(m => ({ default: m.Settings })))
const NotFound     = lazy(() => import('@/pages/NotFound').then(m => ({ default: m.NotFound })))

// ── Loading fallback (skeleton tipis, tidak flash putih) ──────
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="flex flex-col items-center gap-3 opacity-50">
        <div className="w-8 h-8 border-2 border-current border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-mono tracking-widest uppercase">Loading</span>
      </div>
    </div>
  )
}

// ── React Query client ────────────────────────────────────────
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

// ── Auth guard ────────────────────────────────────────────────
function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RequirePermission({
  permission,
  children,
}: {
  permission: string
  children: React.ReactNode
}) {
  const can = useAuthStore((s) => s.can)
  if (!can(permission)) return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

// ── Theme initialiser ─────────────────────────────────────────
function ThemeInit() {
  const theme = useThemeStore((s) => s.theme)
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [theme])
  return null
}

// ── App ───────────────────────────────────────────────────────
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* ── Lenis Smooth Scroll ── */}
      <ReactLenis
        root
        options={{
          lerp: 0.08,
          duration: 1.2,
          smoothWheel: true,
          wheelMultiplier: 0.8,
        }}
      >
        <BrowserRouter>
          <ThemeInit />
          <Toaster
            position="top-right"
            toastOptions={{
              className: '!font-mono !text-xs',
              style: {
                background: 'var(--toast-bg, #FDFCF7)',
                color: 'var(--toast-fg, #3D405B)',
                border: '1px solid var(--toast-border, #e0dcc8)',
              },
            }}
          />

          {/* ── Suspense membungkus semua Routes ── */}
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Public */}
              <Route path="/login" element={<Login />} />

              {/* Protected */}
              <Route
                path="/"
                element={
                  <RequireAuth>
                    <AppLayout />
                  </RequireAuth>
                }
              >
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<Dashboard />} />
                <Route path="live" element={
                  <RequirePermission permission="view_live">
                    <LiveMonitor />
                  </RequirePermission>
                } />
                <Route path="transactions" element={
                  <RequirePermission permission="view_transactions">
                    <Transactions />
                  </RequirePermission>
                } />
                <Route path="analytics" element={
                  <RequirePermission permission="view_analytics">
                    <Analytics />
                  </RequirePermission>
                } />
                <Route path="cases" element={
                  <RequirePermission permission="approve_review">
                    <Cases />
                  </RequirePermission>
                } />
                <Route path="users" element={
                  <RequirePermission permission="manage_users">
                    <Users />
                  </RequirePermission>
                } />
                <Route path="models" element={
                  <RequirePermission permission="manage_model">
                    <Models />
                  </RequirePermission>
                } />
                <Route path="audit" element={
                  <RequirePermission permission="view_audit">
                    <Audit />
                  </RequirePermission>
                } />
                <Route path="settings" element={<Settings />} />
              </Route>

              {/* 404 */}
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </ReactLenis>

      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}