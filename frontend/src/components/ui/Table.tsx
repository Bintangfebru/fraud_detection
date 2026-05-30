import { cn } from '@/utils/format'

interface Column<T> {
  key: string
  header: string
  render?: (row: T) => React.ReactNode
  className?: string
}

interface TableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (row: T) => string
  onRowClick?: (row: T) => void
  emptyMessage?: string
}

export function Table<T>({ columns, data, keyExtractor, onRowClick, emptyMessage = 'No data' }: TableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/40 dark:border-white/06">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'px-5 py-3 text-left text-[10px] uppercase tracking-wider text-stone-400 dark:text-white/30 font-mono',
                  col.className,
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-5 py-10 text-center text-stone-400 dark:text-white/30 font-mono text-xs">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row) => (
              <tr
                key={keyExtractor(row)}
                onClick={() => onRowClick?.(row)}
                className={cn(
                  'border-b border-white/30 dark:border-white/04 transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-white/30 dark:hover:bg-white/03',
                )}
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn('px-5 py-3 text-ink-800 dark:text-white/70 font-body', col.className)}>
                    {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
