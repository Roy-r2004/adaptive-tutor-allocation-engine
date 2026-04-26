import { ArrowLeft, ExternalLink, Hash, Loader2 } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { CategoryBadge } from '@/components/shared/CategoryBadge'
import { PriorityIndicator } from '@/components/shared/PriorityIndicator'
import { QueuePill } from '@/components/shared/QueuePill'
import { useTicket } from '@/lib/queries'
import { formatAbsolute, formatRelative, formatSlaMinutes, formatUsd, shortId } from '@/lib/format'
import type {
  ExtractedEntity,
  FinalOutput,
  TicketStatusResponse,
} from '@/lib/schemas'
import { cn } from '@/lib/utils'

export function TicketDetail() {
  const { id = '' } = useParams<{ id: string }>()
  const { data: ticket, error } = useTicket(id)

  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border bg-bg-subtle/40">
        <div className="mx-auto w-full max-w-4xl px-5 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-[12.5px] text-text-muted hover:text-text"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Chat
            </Link>
            <span className="text-text-muted">/</span>
            <span className="inline-flex items-center gap-1.5 font-mono text-[13px] text-text">
              <Hash className="h-3 w-3 text-text-muted" />
              {shortId(id)}
            </span>
          </div>
          <StatusBadge ticket={ticket} error={!!error} />
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-5 sm:px-6 py-8 space-y-6">
        {error && (
          <Card>
            <CardContent className="text-sm text-danger pt-5">
              Couldn&apos;t load this ticket. {(error as Error).message}
            </CardContent>
          </Card>
        )}

        {!ticket && !error && <DetailSkeleton />}

        {ticket && (
          <>
            <Meta ticket={ticket} />
            {ticket.final_output ? (
              <FinalOutputDetail final={ticket.final_output} />
            ) : (
              <Pending status={ticket.status} />
            )}
          </>
        )}
      </main>
    </div>
  )
}

function StatusBadge({
  ticket,
  error,
}: {
  ticket: TicketStatusResponse | undefined
  error: boolean
}) {
  if (error) return <Badge variant="danger">unreachable</Badge>
  if (!ticket) return <Badge variant="muted">loading</Badge>
  if (ticket.status === 'resolved') return <Badge variant="success">resolved</Badge>
  if (ticket.status === 'awaiting_review') return <Badge variant="warning">awaiting review</Badge>
  return <Badge variant="accent">processing</Badge>
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-48 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  )
}

function Pending({ status }: { status: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 pt-5 text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-accent" />
        <span className="text-sm">
          {status === 'awaiting_review'
            ? 'Paused for human review — resolve it from the reviewer dashboard.'
            : 'Triage pipeline in progress…'}
        </span>
      </CardContent>
    </Card>
  )
}

function Meta({ ticket }: { ticket: TicketStatusResponse }) {
  return (
    <Card>
      <CardContent className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-3 pt-5 text-[12.5px]">
        <Field label="Created" value={formatAbsolute(ticket.created_at)} />
        <Field label="Updated" value={formatRelative(ticket.updated_at)} />
        <Field label="Handled by" value={ticket.handled_by ?? '—'} />
        <Field
          label="Pending escalation"
          value={ticket.has_pending_escalation ? 'yes' : 'no'}
          tone={ticket.has_pending_escalation ? 'warning' : undefined}
        />
      </CardContent>
    </Card>
  )
}

function Field({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: 'warning' | 'success' | 'danger'
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <span className="text-[10.5px] uppercase tracking-wider text-text-muted">{label}</span>
      <span
        className={cn(
          'font-mono text-[12.5px] truncate',
          tone === 'warning' && 'text-warning',
          tone === 'success' && 'text-success',
          tone === 'danger' && 'text-danger',
        )}
      >
        {value}
      </span>
    </div>
  )
}

function FinalOutputDetail({ final }: { final: FinalOutput }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="text-[10.5px] uppercase tracking-wider text-text-muted">
            Human summary
          </div>
        </CardHeader>
        <CardContent className="text-[14px] leading-relaxed">{final.human_summary}</CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <span className="text-[10.5px] uppercase tracking-wider text-text-muted">
                Classification
              </span>
              <span className="font-mono text-[11px] text-text-muted">
                conf {(final.classification.confidence * 100).toFixed(0)}%
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <CategoryBadge category={final.classification.category} />
              <PriorityIndicator priority={final.classification.priority} />
            </div>
            <p className="text-[12.5px] text-text-muted leading-relaxed">
              {final.classification.rationale}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <span className="text-[10.5px] uppercase tracking-wider text-text-muted">
                Routing
              </span>
              <Badge variant="muted">
                <span className="font-mono">{final.routing.decided_by}</span>
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <QueuePill queue={final.routing.queue} />
              <span className="text-[12px] text-text-muted">
                SLA <span className="font-mono text-text">{formatSlaMinutes(final.routing.sla_minutes)}</span>
              </span>
            </div>
            <p className="text-[12.5px] text-text-muted leading-relaxed">
              {final.routing.rationale}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <span className="text-[10.5px] uppercase tracking-wider text-text-muted">
            Enrichment
          </span>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[13px]">{final.enrichment.issue_summary}</p>
          <EntityRow label="Affected IDs" entities={final.enrichment.affected_ids} />
          <EntityRow label="Error codes" entities={final.enrichment.error_codes} />
          {final.enrichment.invoice_amounts_usd.length > 0 && (
            <div className="space-y-1.5">
              <Label>Invoice amounts</Label>
              <div className="flex flex-wrap gap-1.5">
                {final.enrichment.invoice_amounts_usd.map((amt, i) => (
                  <span
                    key={i}
                    className="font-mono text-[11px] rounded border border-warning/30 bg-warning/5 text-warning px-1.5 py-0.5"
                  >
                    {formatUsd(amt)}
                  </span>
                ))}
              </div>
            </div>
          )}
          <EntityRow label="Urgency signals" entities={final.enrichment.urgency_signals} />
        </CardContent>
      </Card>

      {final.escalation.reasons.length > 0 && (
        <Card>
          <CardHeader>
            <span className="text-[10.5px] uppercase tracking-wider text-text-muted">
              Escalation reasons
            </span>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {final.escalation.reasons.map((r) => (
              <Badge key={r} variant="warning">
                <span className="font-mono">{r}</span>
              </Badge>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <span className="text-[10.5px] uppercase tracking-wider text-text-muted">
            Reproducibility
          </span>
        </CardHeader>
        <CardContent>
          {Object.keys(final.prompt_versions).length === 0 && !final.trace_id && (
            <span className="text-[12px] text-text-muted">No prompt versions captured.</span>
          )}
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-[11.5px]">
            {Object.entries(final.prompt_versions).map(([step, hash]) => (
              <div key={step} className="flex items-center justify-between gap-3">
                <dt className="text-text-muted">{step}</dt>
                <dd className="font-mono text-text truncate">{hash.slice(0, 12)}…</dd>
              </div>
            ))}
            {final.trace_id && (
              <div className="flex items-center justify-between gap-3">
                <dt className="text-text-muted">trace_id</dt>
                <dd className="font-mono text-text truncate">{final.trace_id}</dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10.5px] uppercase tracking-wider text-text-muted">{children}</div>
  )
}

function EntityRow({ label, entities }: { label: string; entities: ExtractedEntity[] }) {
  if (entities.length === 0) return null
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <ul className="space-y-1.5">
        {entities.map((e, i) => (
          <li key={i} className="flex items-start gap-2 text-[12.5px]">
            <span className="font-mono rounded border border-border bg-bg-subtle text-text px-1.5 py-0.5 shrink-0">
              {e.value}
            </span>
            <span className="text-text-muted leading-relaxed">
              <ExternalLink className="inline h-3 w-3 mr-1 align-text-bottom opacity-60" />
              <span className="italic">&ldquo;{e.source_quote}&rdquo;</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
