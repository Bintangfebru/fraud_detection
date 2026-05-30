import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow, format } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number | null | undefined, currency = 'IDR'): string {
  if (amount == null || isNaN(amount)) return 'Rp0'
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '0'
  return new Intl.NumberFormat('id-ID').format(n)
}

export function formatPercent(n: number | null | undefined, decimals = 1): string {
  if (n == null || isNaN(n)) return '0.0%'
  return `${(n * 100).toFixed(decimals)}%`
}

export function formatScore(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '0.0%'
  return `${(n * 100).toFixed(1)}%`
}

export function timeAgo(date: string): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true })
}

export function formatDate(date: string): string {
  return format(new Date(date), 'dd MMM yyyy HH:mm')
}

export function formatDateShort(date: string): string {
  return format(new Date(date), 'dd MMM')
}

export function truncate(str: string, n = 30): string {
  return str.length > n ? `${str.slice(0, n)}…` : str
}

export function maskCard(card: string): string {
  return card.replace(/\d(?=\d{4})/g, '*')
}