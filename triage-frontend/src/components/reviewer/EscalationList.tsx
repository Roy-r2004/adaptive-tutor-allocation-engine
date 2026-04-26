import { AnimatePresence } from 'framer-motion'
import { ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { EscalationCard } from '@/components/reviewer/EscalationCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { Skeleton } from '@/components/ui/skeleton'
import {
  usePendingEscalations,
  useResolveEscalation,
} from '@/lib/queries'
import { cn } from '@/lib/utils'
import { ApiHttpError } from '@/lib/api'

interface Props {
  className?: string
}

export function EscalationList({ className }: Props) {
  const { data, isLoading, error, refetch, isRefetching } = usePendingEscalations()
  const resolve = useResolveEscalation()

  if (isLoading) {
    return (
      <div className={cn('space-y-3', className)}>
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <EmptyState
        icon={<ShieldCheck className="h-5 w-5" />}
        title="Couldn't load escalations"
        description={
          error instanceof ApiHttpError && error.status
            ? `${error.message} (HTTP ${error.status})`
            : (error as Error).message
        }
      />
    )
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<ShieldCheck className="h-5 w-5 text-success" />}
        title="All caught up"
        description="No pending escalations. New ones land here within seconds — this list auto-refreshes every 5 seconds."
      />
    )
  }

  return (
    <div className={cn('space-y-3 relative', className)}>
      {isRefetching && (
        <div className="absolute -top-7 right-0 text-[10.5px] text-text-muted font-mono">
          refreshing…
        </div>
      )}
      <AnimatePresence initial={false} mode="popLayout">
        {data.map((esc) => (
          <EscalationCard
            key={esc.escalation_id}
            escalation={esc}
            isPending={resolve.isPending}
            onResolve={({ id, payload }) =>
              resolve.mutate(
                { id, payload },
                {
                  onSuccess: (res) => {
                    toast.success(`Escalation ${res.status}`, {
                      description: 'Backend resumed the paused graph.',
                    })
                    refetch()
                  },
                  onError: (err) => {
                    const msg =
                      err instanceof ApiHttpError ? err.message : (err as Error).message
                    toast.error('Failed to resolve escalation', { description: msg })
                  },
                },
              )
            }
          />
        ))}
      </AnimatePresence>
    </div>
  )
}
