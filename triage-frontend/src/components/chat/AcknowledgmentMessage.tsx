import { CheckCircle2, ShieldQuestion } from 'lucide-react'
import { formatSlaMinutes } from '@/lib/format'
import type { Category, FinalOutput, Queue } from '@/lib/schemas'

/**
 * The user-facing reply line shown above the triage details. Composed entirely
 * client-side from the final_output / escalation context — the backend doesn't
 * generate customer-friendly copy (and shouldn't, since this is an *intake*
 * surface, not a Q&A bot). The job here is to acknowledge, set expectations,
 * and never claim to have resolved the underlying issue.
 */

const CATEGORY_PHRASE: Record<Category, string> = {
  bug_report: 'a bug report',
  feature_request: 'a feature request',
  billing_issue: 'a billing question',
  technical_question: 'a technical question',
  incident_outage: 'an outage report',
}

const QUEUE_TEAM: Record<Queue, string> = {
  engineering: 'Engineering',
  billing: 'Billing',
  product: 'Product',
  it_security: 'IT Security',
  fallback: 'on-call triage',
}

export function AcknowledgmentResolved({ final }: { final: FinalOutput }) {
  const phrase = CATEGORY_PHRASE[final.classification.category]
  const team = QUEUE_TEAM[final.routing.queue]
  const sla = formatSlaMinutes(final.routing.sla_minutes)
  const wasReviewed = final.handled_by !== 'auto'

  return (
    <div className="space-y-2.5">
      <p className="flex items-start gap-2 text-[14px] leading-relaxed text-text">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
        <span>
          Got it — this looks like <span className="font-medium">{phrase}</span>.{' '}
          {wasReviewed
            ? 'A reviewer confirmed the routing and sent it to the '
            : "I've routed it to the "}
          <span className="font-medium">{team}</span> team — you&apos;ll hear back within{' '}
          <span className="font-mono">{sla}</span>.
        </span>
      </p>
      {final.enrichment.issue_summary && (
        <p className="ml-6 text-[12.5px] italic text-text-muted leading-relaxed">
          What I understood: {final.enrichment.issue_summary}
        </p>
      )}
    </div>
  )
}

export function AcknowledgmentAwaitingReview({ issueSummary }: { issueSummary?: string }) {
  return (
    <div className="space-y-2.5">
      <p className="flex items-start gap-2 text-[14px] leading-relaxed text-text">
        <ShieldQuestion className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
        <span>
          Got it — I&apos;m running this past a senior reviewer before routing it. You&apos;ll see an
          update here as soon as it&apos;s been triaged.
        </span>
      </p>
      {issueSummary && (
        <p className="ml-6 text-[12.5px] italic text-text-muted leading-relaxed">
          What I understood: {issueSummary}
        </p>
      )}
    </div>
  )
}
