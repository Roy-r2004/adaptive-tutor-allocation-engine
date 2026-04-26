import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Check, ExternalLink, Hash, Pencil, X } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { CategoryBadge } from '@/components/shared/CategoryBadge'
import { PriorityIndicator } from '@/components/shared/PriorityIndicator'
import { QueuePill } from '@/components/shared/QueuePill'
import { EditRoutingDialog, type EditRoutingValue } from '@/components/reviewer/EditRoutingDialog'
import { formatRelative, shortId } from '@/lib/format'
import { cn } from '@/lib/utils'
import {
  ClassificationSchema,
  RoutingSchema,
  parseReason,
  type EscalationListItem,
  type EscalationResolveRequest,
  type Routing,
  type Classification,
} from '@/lib/schemas'

interface Props {
  escalation: EscalationListItem
  onResolve(input: { id: string; payload: EscalationResolveRequest }): void
  isPending?: boolean
}

function pickProposed(payload: Record<string, unknown>) {
  const cls = ClassificationSchema.safeParse(payload.classification)
  const rt = RoutingSchema.safeParse(payload.routing)
  return {
    classification: cls.success ? cls.data : null,
    routing: rt.success ? rt.data : null,
    body: typeof payload.body === 'string' ? payload.body : '',
  }
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
    case 'incident_category':
      return 'incident category'
    case 'classifier_invalid':
      return 'classifier failed validation'
    default:
      return r.kind.replaceAll('_', ' ')
  }
}

function reasonVariant(raw: string): 'danger' | 'warning' | 'accent' | 'muted' {
  const kind = parseReason(raw).kind
  if (kind === 'incident_category' || kind === 'classifier_invalid') return 'danger'
  if (kind === 'keyword_match' || kind === 'billing_threshold') return 'warning'
  if (kind === 'low_confidence') return 'accent'
  return 'muted'
}

export function EscalationCard({ escalation, onResolve, isPending }: Props) {
  const [editOpen, setEditOpen] = useState(false)
  const [confirmReject, setConfirmReject] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  const proposed = pickProposed(escalation.payload)
  const ticketLink = `/ticket/${escalation.ticket_id}`

  const handleAccept = () =>
    onResolve({
      id: escalation.escalation_id,
      payload: { action: 'accept', reviewer: 'reviewer' },
    })

  const handleEditSubmit = (v: EditRoutingValue) => {
    onResolve({
      id: escalation.escalation_id,
      payload: {
        action: 'edit',
        reviewer: 'reviewer',
        routing: v,
        reason: v.rationale ?? null,
      },
    })
    setEditOpen(false)
  }

  const handleReject = () => {
    if (!rejectReason.trim()) return
    onResolve({
      id: escalation.escalation_id,
      payload: { action: 'reject', reviewer: 'reviewer', reason: rejectReason.trim() },
    })
    setConfirmReject(false)
    setRejectReason('')
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <Card data-testid="escalation-card" className="overflow-hidden">
        <CardHeader className="flex-row items-start justify-between gap-3 space-y-0 pb-2">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-[11px] text-text-muted">
              <span>Pending · created {formatRelative(escalation.created_at)}</span>
            </div>
            <Link
              to={ticketLink}
              className="group inline-flex items-center gap-1.5 font-mono text-[12.5px] text-text hover:text-accent transition-colors"
            >
              <Hash className="h-3 w-3 text-text-muted" />
              <span>{shortId(escalation.ticket_id)}</span>
              <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
          </div>
          <div className="flex flex-wrap justify-end gap-1.5">
            {escalation.reasons.map((r) => (
              <Badge key={r} variant={reasonVariant(r)}>
                <span className="font-mono">{reasonLabel(r)}</span>
              </Badge>
            ))}
          </div>
        </CardHeader>

        <CardContent className="space-y-4 pt-2">
          {proposed.body && (
            <p className="text-[13.5px] leading-relaxed text-text line-clamp-4 whitespace-pre-wrap">
              {proposed.body.length > 320 ? `${proposed.body.slice(0, 320)}…` : proposed.body}
            </p>
          )}

          <ProposedSummary classification={proposed.classification} routing={proposed.routing} />

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="success"
              size="sm"
              onClick={handleAccept}
              disabled={isPending}
              data-testid="action-accept"
            >
              <Check className="h-4 w-4" /> Accept
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setEditOpen(true)}
              disabled={isPending}
              data-testid="action-edit"
            >
              <Pencil className="h-4 w-4" /> Edit
            </Button>
            {!confirmReject ? (
              <Button
                variant="danger"
                size="sm"
                onClick={() => setConfirmReject(true)}
                disabled={isPending}
                data-testid="action-reject"
              >
                <X className="h-4 w-4" /> Reject
              </Button>
            ) : (
              <div className="flex w-full sm:w-auto sm:flex-1 items-center gap-2">
                <input
                  type="text"
                  autoFocus
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Why are we rejecting?"
                  className={cn(
                    'flex h-8 flex-1 rounded-md border border-border bg-surface px-3 text-sm',
                    'placeholder:text-text-muted',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger/40',
                  )}
                />
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleReject}
                  disabled={!rejectReason.trim() || isPending}
                  data-testid="action-reject-confirm"
                >
                  Confirm reject
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setConfirmReject(false)
                    setRejectReason('')
                  }}
                >
                  Cancel
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <EditRoutingDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        initial={proposed.routing}
        currentPriority={proposed.classification?.priority ?? 'medium'}
        onSubmit={handleEditSubmit}
      />
    </motion.div>
  )
}

function ProposedSummary({
  classification,
  routing,
}: {
  classification: Classification | null
  routing: Routing | null
}) {
  if (!classification && !routing) {
    return (
      <div className="text-[12px] text-text-muted">
        No auto-classification yet — pipeline escalated before completion.
      </div>
    )
  }

  return (
    <div className="rounded-md border border-border bg-bg-subtle/40 px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        {classification && (
          <>
            <CategoryBadge category={classification.category} />
            <PriorityIndicator priority={classification.priority} />
            <span className="text-[11px] text-text-muted font-mono">
              conf {(classification.confidence * 100).toFixed(0)}%
            </span>
          </>
        )}
        {routing && (
          <>
            <span className="text-text-muted text-[11px]">→</span>
            <QueuePill queue={routing.queue} />
            <span className="text-[11px] text-text-muted">SLA {routing.sla_minutes}m</span>
          </>
        )}
      </div>
    </div>
  )
}
