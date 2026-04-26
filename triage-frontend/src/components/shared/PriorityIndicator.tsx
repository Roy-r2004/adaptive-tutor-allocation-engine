import { cn } from '@/lib/utils'
import type { Priority } from '@/lib/schemas'

interface Props {
  priority: Priority
  showLabel?: boolean
  className?: string
}

const DOT_COLOR: Record<Priority, string> = {
  high: 'bg-danger',
  medium: 'bg-warning',
  low: 'bg-text-muted',
}

const LABEL: Record<Priority, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export function PriorityIndicator({ priority, showLabel = true, className }: Props) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs font-medium text-text-muted',
        className,
      )}
    >
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          DOT_COLOR[priority],
          priority === 'high' && 'shadow-[0_0_0_3px_rgb(var(--color-danger)/0.18)]',
        )}
      />
      {showLabel && <span>{LABEL[priority]}</span>}
    </span>
  )
}
