import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ExternalLink, Hash } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { PipelineTimeline, type Stage } from '@/components/shared/PipelineTimeline'
import { useEscalationForTicket, useTicket } from '@/lib/queries'
import { shortId } from '@/lib/format'
import { FinalOutputCard } from '@/components/chat/FinalOutputCard'
import {
  AcknowledgmentAwaitingReview,
  AcknowledgmentResolved,
} from '@/components/chat/AcknowledgmentMessage'
import { CategoryBadge } from '@/components/shared/CategoryBadge'
import { PriorityIndicator } from '@/components/shared/PriorityIndicator'
import { QueuePill } from '@/components/shared/QueuePill'
import {
  ClassificationSchema,
  EnrichmentSchema,
  RoutingSchema,
  parseReason,
  type EscalationListItem,
  type TicketStatusResponse,
} from '@/lib/schemas'

interface Props {
  ticketId: string
}

/**
 * The pipeline backend only persists 3 ticket statuses (received, awaiting_review,
 * resolved) — the intermediate "classifying / enriching / routing" steps run inside
 * the worker but aren't surfaced. We animate through them visually while polling so
 * the user gets feedback. The animation snaps to the real outcome the moment polling
 * resolves it, so we're never lying about the state.
 */
const ANIM_STAGES: Stage[] = ['received', 'classifying', 'enriching', 'routing', 'finalizing']
const STAGE_INTERVAL_MS = 900

function deriveStage(ticket: TicketStatusResponse | undefined, elapsedMs: number): Stage {
  if (!ticket) return 'received'
  if (ticket.status === 'resolved') return 'resolved'
  if (ticket.status === 'awaiting_review') return 'awaiting_review'
  // Backend status === "received" while it's still working. Walk the visual stages.
  const idx = Math.min(ANIM_STAGES.length - 1, Math.floor(elapsedMs / STAGE_INTERVAL_MS))
  return ANIM_STAGES[idx]!
}

export function TicketStatusCard({ ticketId }: Props) {
  const { data: ticket, error } = useTicket(ticketId)
  const { escalation } = useEscalationForTicket(
    ticket?.status === 'awaiting_review' ? ticketId : undefined,
  )
  // Drive the visual stage progression off an interval-bumped counter so we never
  // call Date.now() inside render (which the react-hooks/purity lint rule blocks).
  const [elapsedMs, setElapsedMs] = useState(0)

  useEffect(() => {
    if (ticket?.status === 'resolved' || ticket?.status === 'awaiting_review') return
    const start = performance.now()
    const t = setInterval(() => setElapsedMs(performance.now() - start), 250)
    return () => clearInterval(t)
  }, [ticket?.status])

  const stage = useMemo(() => deriveStage(ticket, elapsedMs), [ticket, elapsedMs])

  const outcome: 'resolved' | 'awaiting_review' | null =
    ticket?.status === 'resolved'
      ? 'resolved'
      : ticket?.status === 'awaiting_review'
        ? 'awaiting_review'
        : null

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
      className="ml-10 max-w-[78%]"
    >
      <Card>
        <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
          <div className="flex flex-col gap-1">
            <span className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
              Triage pipeline
            </span>
            <Link
              to={`/ticket/${ticketId}`}
              className="group inline-flex items-center gap-1.5 font-mono text-[12px] text-text hover:text-accent transition-colors"
            >
              <Hash className="h-3 w-3 text-text-muted" />
              <span>{shortId(ticketId)}</span>
              <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
          </div>
          <StatusBadge ticket={ticket} error={!!error} />
        </CardHeader>
        <CardContent>
          {error && (
            <p className="text-sm text-danger">
              Couldn&apos;t reach the triage backend. The ticket was queued — check{' '}
              <code className="font-mono">/healthz</code>.
            </p>
          )}

          {!ticket && !error && (
            <div className="space-y-2.5">
              <Skeleton className="h-3 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
              <Skeleton className="h-3 w-1/4" />
            </div>
          )}

          {ticket && (
            <>
              <PipelineTimeline current={stage} outcome={outcome} />
              {ticket.status === 'awaiting_review' && (
                <div className="mt-5 space-y-4">
                  <AcknowledgmentAwaitingReview
                    issueSummary={
                      EnrichmentSchema.safeParse(escalation?.payload.enrichment).data?.issue_summary
                    }
                  />
                  <EscalationCallout escalation={escalation} ticketId={ticketId} />
                </div>
              )}
              {ticket.status === 'resolved' && ticket.final_output && (
                <div className="mt-5 space-y-4">
                  <AcknowledgmentResolved final={ticket.final_output} />
                  <FinalOutputCard final={ticket.final_output} />
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}

function StatusBadge({
  ticket,
  error,
}: {
  ticket: TicketStatusResponse | undefined
  error: boolean
}) {
  if (error) return <Badge variant="danger">backend unreachable</Badge>
  if (!ticket) return <Badge variant="muted">queued</Badge>
  if (ticket.status === 'resolved') return <Badge variant="success">resolved</Badge>
  if (ticket.status === 'awaiting_review') return <Badge variant="warning">awaiting review</Badge>
  return <Badge variant="accent">processing</Badge>
}

function reasonLabel(raw: string): string {
  const r = parseReason(raw)
  switch (r.kind) {
    case 'low_confidence':
      return r.value ? `low confidence · ${r.value}` : 'low confidence'
    case 'keyword_match':
      return r.value ? `keyword · ${r.value}` : 'keyword match'
    case 'billing_threshold':
      return r.value ? `billing > $${r.value}` : 'billing threshold'
    case 'category_incident_outage':
    case 'incident_category':
      return 'incident category'
    case 'classifier_invalid':
      return 'classifier failed validation'
    default:
      return r.kind.replaceAll('_', ' ')
  }
}

function EscalationCallout({
  escalation,
  ticketId,
}: {
  escalation: EscalationListItem | undefined
  ticketId: string
}) {
  const proposed = escalation
    ? {
        classification: ClassificationSchema.safeParse(escalation.payload.classification).data,
        routing: RoutingSchema.safeParse(escalation.payload.routing).data,
      }
    : null

  return (
    <div className="rounded-md border border-warning/30 bg-warning/5 p-3.5 space-y-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-warning">
        Why it&apos;s being reviewed
      </p>

      {escalation && escalation.reasons.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {escalation.reasons.map((r) => (
            <Badge key={r} variant="warning">
              <span className="font-mono">{reasonLabel(r)}</span>
            </Badge>
          ))}
        </div>
      )}

      {proposed && (proposed.classification || proposed.routing) && (
        <div className="flex flex-wrap items-center gap-2">
          {proposed.classification && (
            <>
              <CategoryBadge category={proposed.classification.category} />
              <PriorityIndicator priority={proposed.classification.priority} />
            </>
          )}
          {proposed.routing && (
            <>
              <span className="text-text-muted text-[11px]">→</span>
              <QueuePill queue={proposed.routing.queue} />
            </>
          )}
        </div>
      )}

      <p className="text-[12.5px] text-text-muted leading-relaxed">
        Track progress on the{' '}
        <Link
          to={`/ticket/${ticketId}`}
          className="font-medium text-accent hover:underline underline-offset-2"
        >
          ticket page
        </Link>{' '}
        or jump to the{' '}
        <Link to="/reviewer" className="font-medium text-accent hover:underline underline-offset-2">
          reviewer dashboard
        </Link>
        .
      </p>
    </div>
  )
}
