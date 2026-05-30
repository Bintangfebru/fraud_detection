import { cn } from '@/utils/format'

// Generic skeleton block
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('skeleton', className)} />
}

export function StatCardSkeleton() {
  return (
    <div className="glass-stat p-5 flex flex-col gap-3">
      <div className="skeleton h-4 w-24" />
      <div className="skeleton h-10 w-32" />
      <div className="skeleton h-3 w-20" />
    </div>
  )
}

export function ChartSkeleton({ height = 200 }: { height?: number }) {
  return <div className="skeleton w-full rounded-2xl" style={{ height }} />
}

export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="skeleton h-3 w-full max-w-[100px]" />
        </td>
      ))}
    </tr>
  )
}