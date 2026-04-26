import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-md bg-bg-subtle',
        'bg-[linear-gradient(90deg,transparent,rgb(var(--color-border-strong)/0.4),transparent)]',
        'bg-[length:200%_100%] animate-shimmer',
        className,
      )}
      {...props}
    />
  )
}
