import { Check, Loader2, AlertCircle } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

export type Stage =
  | 'received'
  | 'classifying'
  | 'enriching'
  | 'routing'
  | 'finalizing'
  | 'resolved'
  | 'awaiting_review'

const STAGE_LABELS: Record<Exclude<Stage, 'resolved' | 'awaiting_review'>, string> = {
  received: 'Received',
  classifying: 'Classifying intent',
  enriching: 'Extracting entities',
  routing: 'Routing to queue',
  finalizing: 'Generating summary',
}

const ORDER: Stage[] = ['received', 'classifying', 'enriching', 'routing', 'finalizing']

type Status = 'pending' | 'active' | 'done' | 'warn'

interface Props {
  /** The stage currently active. */
  current: Stage
  /** If awaiting human review, the trailing dot turns warn. */
  outcome?: 'resolved' | 'awaiting_review' | null
  className?: string
}

function statusFor(stage: Exclude<Stage, 'resolved' | 'awaiting_review'>, current: Stage): Status {
  if (current === 'resolved' || current === 'awaiting_review') return 'done'
  const ci = ORDER.indexOf(current)
  const si = ORDER.indexOf(stage)
  if (si < ci) return 'done'
  if (si === ci) return 'active'
  return 'pending'
}

export function PipelineTimeline({ current, outcome, className }: Props) {
  const stages = ORDER as Exclude<Stage, 'resolved' | 'awaiting_review'>[]

  return (
    <ol className={cn('relative ml-1 flex flex-col gap-3', className)}>
      {stages.map((stage, idx) => {
        const status = statusFor(stage, current)
        const isLast = idx === stages.length - 1
        return (
          <li key={stage} className="relative flex items-start gap-3">
            {!isLast && (
              <span
                aria-hidden
                className={cn(
                  'absolute left-[11px] top-[22px] w-px h-[calc(100%-2px)]',
                  status === 'done' ? 'bg-accent/30' : 'bg-border',
                )}
              />
            )}
            <Dot status={status} />
            <div className="flex-1 pt-0.5">
              <div
                className={cn(
                  'text-sm font-medium leading-tight',
                  status === 'pending' && 'text-text-muted',
                  status === 'active' && 'text-text',
                  status === 'done' && 'text-text',
                )}
              >
                {STAGE_LABELS[stage]}
              </div>
            </div>
          </li>
        )
      })}
      <li className="relative flex items-start gap-3 pt-1">
        <FinalDot outcome={outcome} />
        <div className="flex-1 pt-0.5">
          <div className="text-sm font-medium leading-tight">
            {outcome === 'resolved' && <span className="text-success">Resolved</span>}
            {outcome === 'awaiting_review' && (
              <span className="text-warning">Awaiting human review</span>
            )}
            {!outcome && <span className="text-text-muted">Awaiting outcome</span>}
          </div>
        </div>
      </li>
    </ol>
  )
}

function Dot({ status }: { status: Status }) {
  if (status === 'active') {
    return (
      <motion.span
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-accent/40 bg-accent/10"
      >
        <Loader2 className="h-3 w-3 animate-spin text-accent" />
      </motion.span>
    )
  }
  if (status === 'done') {
    return (
      <span className="relative z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-accent/30 bg-accent text-white">
        <Check className="h-3 w-3" />
      </span>
    )
  }
  return (
    <span className="relative z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-border bg-surface">
      <span className="h-1.5 w-1.5 rounded-full bg-border-strong" />
    </span>
  )
}

function FinalDot({ outcome }: { outcome?: 'resolved' | 'awaiting_review' | null }) {
  if (outcome === 'resolved') {
    return (
      <span className="relative z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-success/30 bg-success text-white">
        <Check className="h-3 w-3" />
      </span>
    )
  }
  if (outcome === 'awaiting_review') {
    return (
      <span className="relative z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-warning/30 bg-warning text-white">
        <AlertCircle className="h-3 w-3" />
      </span>
    )
  }
  return (
    <span className="relative z-10 flex h-[22px] w-[22px] items-center justify-center rounded-full border border-dashed border-border-strong bg-surface">
      <span className="h-1.5 w-1.5 rounded-full bg-border-strong animate-pulse-dot" />
    </span>
  )
}
