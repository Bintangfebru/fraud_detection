import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileText, Search } from 'lucide-react'
import { apiClient } from '@/api/client'
import { type AuditLog } from '@/types/api'
import { type PaginatedResponse } from '@/types/api'
import { Card, CardHeader } from '@/components/ui/Card'
import { ErrorState, EmptyState } from '@/components/ui/ErrorState'
import { TableRowSkeleton } from '@/components/ui/Skeleton'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { formatDate } from '@/utils/format'

async function getAuditLogs(page = 1, pageSize = 50): Promise<PaginatedResponse<AuditLog>> {
  const { data } = await apiClient.get<PaginatedResponse<AuditLog>>(
    `/api/v1/audit?page=${page}&page_size=${pageSize}`,
  )
  return data
}

const ACTION_COLORS: Record<string, 'fraud' | 'review' | 'safe' | 'info' | 'neutral'> = {
  CREATE: 'safe',
  UPDATE: 'review',
  DELETE: 'fraud',
  LOGIN: 'info',
  LOGOUT: 'neutral',
  APPROVE: 'safe',
  REJECT: 'fraud',
}

export function Audit() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')

  const logs = useQuery({
    queryKey: ['audit', page],
    queryFn: ({ signal: _signal }) => getAuditLogs(page, 50),
    placeholderData: (prev) => prev,
  })

  const totalPages = logs.data ? Math.ceil(logs.data.total / 50) : 0

  const filtered = search
    ? logs.data?.items.filter(
        (l) =>
          l.action.toLowerCase().includes(search.toLowerCase()) ||
          l.actor.toLowerCase().includes(search.toLowerCase()) ||
          l.resource_type.toLowerCase().includes(search.toLowerCase()),
      )
    : logs.data?.items

  function getActionVariant(action: string) {
    const key = Object.keys(ACTION_COLORS).find((k) => action.toUpperCase().includes(k))
    return key ? ACTION_COLORS[key] : 'neutral'
  }

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── Search ───────────────────────────────────────────── */}
      <Card className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-warm-400" />
          <input
            type="text"
            placeholder="Filter by action, actor, or resource…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-9 pl-9 pr-3 text-sm font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none text-navy-700 dark:text-warm-100 placeholder:text-warm-400"
          />
        </div>
        <div className="text-xs font-mono text-warm-500 dark:text-warm-400 flex items-center">
          {logs.data ? `${logs.data.total.toLocaleString()} log entries` : '—'}
        </div>
      </Card>

      {/* ── Log Table ─────────────────────────────────────────── */}
      <Card noPad>
        <div className="p-5 pb-0">
          <CardHeader title="Audit Log" subtitle="System event trail" />
        </div>
        <div className="overflow-x-auto max-h-[70vh] overflow-y-auto scrollbar-thin">
          <table className="w-full text-xs font-mono">
            <thead className="sticky top-0 bg-warm-50 dark:bg-navy-800 z-10">
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['Timestamp', 'Actor', 'Action', 'Resource', 'ID', 'Details'].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {logs.isLoading ? (
                Array.from({ length: 12 }).map((_, i) => <TableRowSkeleton key={i} cols={6} />)
              ) : logs.isError ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12">
                    <ErrorState message="Failed to load audit log" onRetry={() => logs.refetch()} />
                  </td>
                </tr>
              ) : filtered?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12">
                    <EmptyState
                      icon={<FileText className="w-6 h-6" />}
                      title="No log entries found"
                      description={search ? 'Try a different search term' : 'No events recorded yet'}
                    />
                  </td>
                </tr>
              ) : (
                filtered?.map((log) => (
                  <tr
                    key={log.id}
                    className="border-b border-warm-200/60 dark:border-navy-700/50 hover:bg-warm-100 dark:hover:bg-navy-700/30 transition-colors"
                  >
                    <td className="px-4 py-2 text-warm-500 dark:text-warm-400 whitespace-nowrap">
                      {formatDate(log.created_at)}
                    </td>
                    <td className="px-4 py-2 font-semibold text-navy-700 dark:text-warm-200">
                      {log.actor}
                    </td>
                    <td className="px-4 py-2">
                      <Badge variant={getActionVariant(log.action)} size="sm">
                        {log.action}
                      </Badge>
                    </td>
                    <td className="px-4 py-2 text-warm-500 dark:text-warm-400 uppercase">
                      {log.resource_type}
                    </td>
                    <td className="px-4 py-2 text-warm-400 dark:text-warm-500 truncate max-w-[80px]">
                      {log.resource_id}
                    </td>
                    <td className="px-4 py-2 text-warm-500 dark:text-warm-400 max-w-[200px] truncate">
                      {log.metadata && Object.keys(log.metadata).length > 0
                        ? Object.entries(log.metadata)
                            .slice(0, 2)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(', ')
                        : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-warm-200 dark:border-navy-700">
            <span className="text-xs font-mono text-warm-500">
              Page {page} of {totalPages}
            </span>
            <div className="flex gap-1">
              <Button
                variant="ghost"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Prev
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}