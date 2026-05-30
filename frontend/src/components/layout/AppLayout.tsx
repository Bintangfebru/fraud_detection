import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

const PAGE_TITLES: Record<string, { title: string; breadcrumb?: string }> = {
  '/dashboard':    { title: 'Dashboard', breadcrumb: 'Overview' },
  '/live':         { title: 'Live Monitor', breadcrumb: 'Overview' },
  '/transactions': { title: 'Transactions', breadcrumb: 'Investigation' },
  '/analytics':    { title: 'Analytics', breadcrumb: 'Investigation' },
  '/cases':        { title: 'Case Management', breadcrumb: 'Investigation' },
  '/users':        { title: 'User Management', breadcrumb: 'Administration' },
  '/models':       { title: 'Model Manager', breadcrumb: 'Administration' },
  '/audit':        { title: 'Audit Log', breadcrumb: 'Administration' },
  '/settings':     { title: 'Settings', breadcrumb: 'Administration' },
}

export function AppLayout() {
  const location = useLocation()
  const pageInfo = PAGE_TITLES[location.pathname] ?? { title: 'FraudShield' }

  return (
    <div className="relative min-h-screen bg-sage-100 dark:bg-ink-900 overflow-hidden">
      {/* Organic background blobs */}
      <div className="bg-blob" />
      <div className="bg-blob-extra" />

      {/* Layout */}
      <div className="relative z-10 flex flex-col min-h-screen">
        <Topbar
          title={pageInfo.title}
          breadcrumb={pageInfo.breadcrumb}
        />
        <main className="flex-1 pt-[60px] pb-28">
          <div className="p-6 animate-fade-in">
            <Outlet />
          </div>
        </main>
      </div>

      {/* Floating bottom nav */}
      <Sidebar />
    </div>
  )
}