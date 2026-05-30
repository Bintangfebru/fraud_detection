import { useState, memo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Download, Filter, ChevronLeft, ChevronRight, Eye, CheckCircle, XCircle } from 'lucide-react'
import { getTransactions, getTransactionDetail, updateReview } from '@/api/fraud'
import { queryKeys } from '@/lib/queryKeys'
import { type TransactionFilters } from '@/api/fraud'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { ErrorState, EmptyState } from '@/components/ui/ErrorState'
import { TableRowSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { formatCurrency, formatDate, formatScore } from '@/utils/format'
import { useAuthStore } from '@/stores/authStore'
import toast from 'react-hot-toast'

const PAGE_SIZE = 20

// ── Memo: tiap baris transaksi ──
const TxRow = memo(function TxRow({ tx, onView }: { tx: any; onView: (ref: string) => void }) {
  return (
    <tr className="border-b border-warm-200/60 dark:border-navy-700/50 hover:bg-warm-100 dark:hover:bg-navy-700/30 transition-colors">
      <td className="px-4 py-2.5 font-semibold text-navy-700 dark:text-warm-200">{tx.reference}</td>
      <td className="px-4 py-2.5 text-warm-600 dark:text-warm-400 max-w-[120px] truncate">{tx.merchant}</td>
      <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400 uppercase">{tx.category.replace('_', ' ')}</td>
      <td className="px-4 py-2.5 text-navy-700 dark:text-warm-200">{formatCurrency(tx.amount, tx.currency)}</td>
      <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400">{tx.city}</td>
      <td className="px-4 py-2.5">
        {tx.fraud_score != null ? (
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 bg-warm-300 dark:bg-navy-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${tx.fraud_score * 100}%`,
                  background: tx.fraud_score > 0.7 ? '#E07A5F' : tx.fraud_score > 0.4 ? '#d4a050' : '#81B29A',
                }}
              />
            </div>
            <span>{formatScore(tx.fraud_score)}</span>
          </div>
        ) : <span className="text-warm-400">—</span>}
      </td>
      <td className="px-4 py-2.5 text-warm-500 dark:text-warm-400 whitespace-nowrap">{formatDate(tx.created_at)}</td>
      <td className="px-4 py-2.5"><StatusBadge status={tx.status} /></td>
      <td className="px-4 py-2.5">
        <Button variant="ghost" size="sm" icon={<Eye className="w-3 h-3" />} onClick={() => onView(tx.reference)}>Detail</Button>
      </td>
    </tr>
  )
})

export function Transactions() {
  const queryClient = useQueryClient()
  const can = useAuthStore((s) => s.can)

  const [filters, setFilters] = useState<TransactionFilters>({ page: 1, page_size: PAGE_SIZE })
  const [search, setSearch] = useState('')
  const [selectedRef, setSelectedRef] = useState<string | null>(null)
  const [reviewNotes, setReviewNotes] = useState('')

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: queryKeys.transactions(filters as Record<string, unknown>),
    queryFn: ({ signal }) => getTransactions(filters, { signal }),
    placeholderData: (prev) => prev,
  })

  const detail = useQuery({
    queryKey: queryKeys.transactionDetail(selectedRef ?? ''),
    queryFn: ({ signal }) => getTransactionDetail(selectedRef!, { signal }),
    enabled: !!selectedRef,
  })

  const reviewMutation = useMutation({
    mutationFn: ({ predictionId, confirmed }: { predictionId: string; confirmed: boolean }) =>
      updateReview(predictionId, confirmed, reviewNotes),
    onSuccess: () => {
      toast.success('Review submitted')
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: queryKeys.transactionDetail(selectedRef ?? '') })
      setReviewNotes('')
    },
    onError: () => toast.error('Review failed'),
  })

  const applySearch = () => setFilters((f) => ({ ...f, merchant: search || undefined, page: 1 }))
  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = filters.page ?? 1

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ── Filters ── */}
      <Card className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-warm-400" />
          <input
            type="text"
            placeholder="Search merchant…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
            className="w-full h-9 pl-9 pr-3 text-sm font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy-700/20 dark:focus:ring-coral-400/20 text-navy-700 dark:text-warm-100 placeholder:text-warm-400"
          />
        </div>
        <select
          className="h-9 px-3 text-xs font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg text-navy-700 dark:text-warm-200 focus:outline-none"
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined, page: 1 }))}
        >
          <option value="">All Status</option>
          <option value="FRAUD">Fraud</option>
          <option value="REVIEW">Review</option>
          <option value="SAFE">Safe</option>
        </select>
        <Button variant="ghost" size="sm" icon={<Filter className="w-3.5 h-3.5" />} onClick={applySearch}>Apply</Button>
        {can('export_data') && (
          <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>Export CSV</Button>
        )}
        <div className="ml-auto text-xs font-mono text-warm-500 dark:text-warm-400">
          {data ? `${data.total.toLocaleString()} records` : '—'}
        </div>
      </Card>

      {/* ── Table ── */}
      <Card noPad>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-warm-200 dark:border-navy-700">
                {['Reference', 'Merchant', 'Category', 'Amount', 'City', 'Risk Score', 'Date', 'Status', ''].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400 font-mono whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 10 }).map((_, i) => <TableRowSkeleton key={i} cols={9} />)
              ) : isError ? (
                <tr><td colSpan={9} className="px-4 py-12"><ErrorState message="Failed to load transactions" onRetry={refetch} /></td></tr>
              ) : data?.items.length === 0 ? (
                <tr><td colSpan={9} className="px-4 py-12"><EmptyState title="No transactions found" description="Try adjusting your filters" /></td></tr>
              ) : (
                data?.items.map((tx) => <TxRow key={tx.id} tx={tx} onView={setSelectedRef} />)
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-warm-200 dark:border-navy-700">
            <span className="text-xs font-mono text-warm-500 dark:text-warm-400">Page {currentPage} of {totalPages}</span>
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" disabled={currentPage === 1 || isFetching} onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))} icon={<ChevronLeft className="w-3.5 h-3.5" />}>Prev</Button>
              <Button variant="ghost" size="sm" disabled={currentPage >= totalPages || isFetching} onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))} icon={<ChevronRight className="w-3.5 h-3.5" />}>Next</Button>
            </div>
          </div>
        )}
      </Card>

      {/* ── Detail Modal ── */}
      <Modal open={!!selectedRef} onClose={() => { setSelectedRef(null); setReviewNotes('') }} title="Transaction Detail" subtitle={selectedRef ?? ''} size="lg">
        {detail.isLoading ? (
          <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-5 w-full" />)}</div>
        ) : detail.isError ? (
          <ErrorState compact message="Failed to load detail" />
        ) : detail.data ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              {[
                ['Merchant', detail.data.merchant],
                ['Category', detail.data.category],
                ['Amount', formatCurrency(detail.data.amount, detail.data.currency)],
                ['Card', detail.data.card_number_masked],
                ['City', detail.data.city],
                ['Date', formatDate(detail.data.created_at)],
              ].map(([k, v]) => (
                <div key={k} className="flex flex-col gap-0.5">
                  <span className="text-[10px] uppercase tracking-wider text-warm-500 dark:text-warm-400">{k}</span>
                  <span className="text-navy-700 dark:text-warm-200 font-semibold">{v}</span>
                </div>
              ))}
            </div>
            {detail.data.prediction && (
              <div className="border border-warm-200 dark:border-navy-700 rounded-lg p-4 space-y-2">
                <div className="text-[10px] font-mono uppercase tracking-wider text-warm-500 dark:text-warm-400 mb-3">ML Prediction</div>
                <div className="flex items-center gap-4">
                  <StatusBadge status={detail.data.prediction.status} />
                  <span className="text-xs font-mono text-warm-500">Score: <strong className="text-navy-700 dark:text-warm-200">{formatScore(detail.data.prediction.fraud_score)}</strong></span>
                  <span className="text-xs font-mono text-warm-500">Model: <strong className="text-navy-700 dark:text-warm-200">{detail.data.prediction.model_version}</strong></span>
                </div>
                {can('approve_review') && !detail.data.prediction.is_reviewed && (
                  <div className="space-y-2 pt-2">
                    <textarea placeholder="Review notes (optional)…" value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} rows={2} className="w-full px-3 py-2 text-xs font-mono bg-warm-100 dark:bg-navy-900 border border-warm-300 dark:border-navy-600 rounded-lg focus:outline-none resize-none text-navy-700 dark:text-warm-200 placeholder:text-warm-400" />
                    <div className="flex gap-2">
                      <Button variant="danger" size="sm" loading={reviewMutation.isPending} icon={<XCircle className="w-3.5 h-3.5" />} onClick={() => reviewMutation.mutate({ predictionId: detail.data!.prediction!.id, confirmed: true })}>Confirm Fraud</Button>
                      <Button variant="primary" size="sm" loading={reviewMutation.isPending} icon={<CheckCircle className="w-3.5 h-3.5" />} onClick={() => reviewMutation.mutate({ predictionId: detail.data!.prediction!.id, confirmed: false })}>Mark Safe</Button>
                    </div>
                  </div>
                )}
                {detail.data.prediction.is_reviewed && (
                  <div className="text-xs font-mono text-warm-500 dark:text-warm-400 pt-1">
                    Reviewed by {detail.data.prediction.reviewed_by} · {detail.data.prediction.review_notes}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null}
      </Modal>
    </div>
  )
}