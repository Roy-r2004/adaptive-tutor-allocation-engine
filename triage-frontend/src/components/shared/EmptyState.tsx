import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: Props) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center px-6 py-16 rounded-lg',
        'border border-dashed border-border bg-surface/40',
        className,
      )}
    >
      {icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-bg-subtle text-text-muted">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold tracking-tightish">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-text-muted text-balance">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
