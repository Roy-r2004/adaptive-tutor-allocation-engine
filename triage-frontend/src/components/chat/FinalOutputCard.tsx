import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { CategoryBadge } from '@/components/shared/CategoryBadge'
import { PriorityIndicator } from '@/components/shared/PriorityIndicator'
import { QueuePill } from '@/components/shared/QueuePill'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { formatSlaMinutes, formatUsd } from '@/lib/format'
import type { FinalOutput } from '@/lib/schemas'

interface Props {
  final: FinalOutput
  className?: string
}

export function FinalOutputCard({ final, className }: Props) {
  const [open, setOpen] = useState(true)
  return (
    <div className={cn('rounded-md border border-border bg-bg-subtle/50 overflow-hidden', className)}>
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={final.classification.category} />
          <PriorityIndicator priority={final.classification.priority} />
          <span className="text-[11px] text-text-muted font-mono">
            confidence {(final.classification.confidence * 100).toFixed(0)}%
          </span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? 'Collapse details' : 'Expand details'}
        >
          <ChevronDown
            className={cn('h-4 w-4 transition-transform', open && 'rotate-180')}
          />
        </Button>
      </div>

      {open && (
        <div className="border-t border-border px-4 py-3.5 space-y-4 bg-surface">
          <Section label="Summary">
            <p className="text-[13px] leading-relaxed">{final.human_summary}</p>
          </Section>

          <Section label="Routing">
            <div className="flex flex-wrap items-center gap-2">
              <QueuePill queue={final.routing.queue} />
              <span className="text-[12px] text-text-muted">
                SLA: <span className="font-mono text-text">{formatSlaMinutes(final.routing.sla_minutes)}</span>
              </span>
              <span className="text-[12px] text-text-muted">
                decided by{' '}
                <span className="font-mono text-text">{final.routing.decided_by}</span>
              </span>
            </div>
            <p className="mt-1.5 text-[12.5px] text-text-muted leading-relaxed">
              {final.routing.rationale}
            </p>
          </Section>

          <Section label="Classification rationale">
            <p className="text-[12.5px] text-text-muted leading-relaxed">
              {final.classification.rationale}
            </p>
          </Section>

          {(final.enrichment.affected_ids.length > 0 ||
            final.enrichment.error_codes.length > 0 ||
            final.enrichment.invoice_amounts_usd.length > 0) && (
            <Section label="Extracted">
              <div className="flex flex-wrap gap-1.5">
                {final.enrichment.affected_ids.map((e, i) => (
                  <Chip key={`id-${i}`} kind="id" value={e.value} />
                ))}
                {final.enrichment.error_codes.map((e, i) => (
                  <Chip key={`err-${i}`} kind="err" value={e.value} />
                ))}
                {final.enrichment.invoice_amounts_usd.map((amount, i) => (
                  <Chip key={`amt-${i}`} kind="amt" value={formatUsd(amount)} />
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="text-[10.5px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </div>
      {children}
    </div>
  )
}

function Chip({ kind, value }: { kind: 'id' | 'err' | 'amt'; value: string }) {
  const styles =
    kind === 'err'
      ? 'border-danger/30 bg-danger/5 text-danger'
      : kind === 'amt'
        ? 'border-warning/30 bg-warning/5 text-warning'
        : 'border-border bg-bg-subtle text-text'
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[11px]',
        styles,
      )}
    >
      {value}
    </span>
  )
}
