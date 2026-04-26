import { formatDistanceToNowStrict, format } from 'date-fns'

export function formatRelative(value: string | Date): string {
  const d = typeof value === 'string' ? new Date(value) : value
  return formatDistanceToNowStrict(d, { addSuffix: true })
}

export function formatAbsolute(value: string | Date): string {
  const d = typeof value === 'string' ? new Date(value) : value
  return format(d, 'MMM d, yyyy · HH:mm:ss')
}

/** Render a UUID compactly as `id[:8]…id[-4:]`. */
export function shortId(id: string): string {
  if (id.length <= 14) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

export function formatSlaMinutes(min: number): string {
  if (min < 60) return `${min}m`
  if (min < 60 * 24) return `${Math.round(min / 60)}h`
  return `${Math.round(min / 60 / 24)}d`
}

export function formatUsd(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}
