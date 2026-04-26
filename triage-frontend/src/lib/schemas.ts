/**
 * Zod schemas mirroring the backend's Pydantic models
 * (triage-pipeline/src/app/schemas/*.py). Keep in sync.
 *
 * Every API response is parsed through these — a Zod failure throws a typed
 * error from the axios response interceptor.
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Enums (Literals on the backend)
// ---------------------------------------------------------------------------

export const CategorySchema = z.enum([
  'bug_report',
  'feature_request',
  'billing_issue',
  'technical_question',
  'incident_outage',
])
export type Category = z.infer<typeof CategorySchema>

export const PrioritySchema = z.enum(['low', 'medium', 'high'])
export type Priority = z.infer<typeof PrioritySchema>

export const QueueSchema = z.enum([
  'engineering',
  'billing',
  'product',
  'it_security',
  'fallback',
])
export type Queue = z.infer<typeof QueueSchema>

export const SourceSchema = z.enum(['chat', 'web_form', 'email', 'api'])
export type Source = z.infer<typeof SourceSchema>

// ---------------------------------------------------------------------------
// Step 2: ClassificationResult
// ---------------------------------------------------------------------------

export const ClassificationSchema = z.object({
  category: CategorySchema,
  priority: PrioritySchema,
  confidence: z.number().min(0).max(1),
  rationale: z.string(),
})
export type Classification = z.infer<typeof ClassificationSchema>

// ---------------------------------------------------------------------------
// Step 3: EnrichmentResult
// ---------------------------------------------------------------------------

export const ExtractedEntitySchema = z.object({
  value: z.string(),
  source_quote: z.string(),
})
export type ExtractedEntity = z.infer<typeof ExtractedEntitySchema>

export const EnrichmentSchema = z.object({
  issue_summary: z.string(),
  affected_ids: z.array(ExtractedEntitySchema).default([]),
  error_codes: z.array(ExtractedEntitySchema).default([]),
  invoice_amounts_usd: z.array(z.number()).default([]),
  urgency_signals: z.array(ExtractedEntitySchema).default([]),
  detected_language: z.string().default('en'),
})
export type Enrichment = z.infer<typeof EnrichmentSchema>

// ---------------------------------------------------------------------------
// Step 4: RoutingResult
// ---------------------------------------------------------------------------

export const RoutingSchema = z.object({
  queue: QueueSchema,
  sla_minutes: z.number().int().min(1),
  rationale: z.string(),
  decided_by: z.enum(['auto', 'hitl']).default('auto'),
  needs_human: z.boolean().default(false),
})
export type Routing = z.infer<typeof RoutingSchema>

// ---------------------------------------------------------------------------
// Step 6: EscalationFlag
// ---------------------------------------------------------------------------

export const EscalationFlagSchema = z.object({
  needs_human: z.boolean().default(false),
  reasons: z.array(z.string()).default([]),
  blocking: z.boolean().default(true),
  proposed_reviewer: z.string().nullable().optional(),
})
export type EscalationFlag = z.infer<typeof EscalationFlagSchema>

// ---------------------------------------------------------------------------
// Step 5: FinalOutput
// ---------------------------------------------------------------------------

export const FinalOutputSchema = z.object({
  ticket_id: z.string(),
  message_id: z.string(),
  source: z.string(),
  received_at: z.string(),
  classification: ClassificationSchema,
  enrichment: EnrichmentSchema,
  routing: RoutingSchema,
  escalation: EscalationFlagSchema,
  human_summary: z.string(),
  handled_by: z.enum(['auto', 'human', 'hybrid']).default('auto'),
  prompt_versions: z.record(z.string(), z.string()).default({}),
  trace_id: z.string().nullable().optional(),
})
export type FinalOutput = z.infer<typeof FinalOutputSchema>

// ---------------------------------------------------------------------------
// HTTP API: ingest, ticket, escalation
// ---------------------------------------------------------------------------

export const IngestRequestSchema = z.object({
  source: SourceSchema,
  body: z.string().min(1).max(10_000),
  customer_id: z.string().nullable().optional(),
  tenant_id: z.string().default('default'),
  extra: z.record(z.string(), z.unknown()).default({}),
})
export type IngestRequest = z.infer<typeof IngestRequestSchema>

export const IngestResponseSchema = z.object({
  message_id: z.string().uuid(),
  ticket_id: z.string().uuid(),
  job_id: z.string(),
  status: z.string().default('queued'),
})
export type IngestResponse = z.infer<typeof IngestResponseSchema>

export const TicketStatusSchema = z.enum([
  'received',
  'awaiting_review',
  'resolved',
])
export type TicketStatus = z.infer<typeof TicketStatusSchema>

export const TicketStatusResponseSchema = z.object({
  ticket_id: z.string().uuid(),
  // Status is currently free-form on the backend ("received" | "awaiting_review" | "resolved")
  // but we don't fail if a future state appears.
  status: z.string(),
  handled_by: z.string().nullable().optional(),
  summary: z.string().nullable().optional(),
  has_pending_escalation: z.boolean().default(false),
  final_output: FinalOutputSchema.nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
})
export type TicketStatusResponse = z.infer<typeof TicketStatusResponseSchema>

export const EscalationListItemSchema = z.object({
  escalation_id: z.string().uuid(),
  ticket_id: z.string().uuid(),
  status: z.string(),
  reasons: z.array(z.string()).default([]),
  payload: z.record(z.string(), z.unknown()).default({}),
  created_at: z.string(),
})
export type EscalationListItem = z.infer<typeof EscalationListItemSchema>

export const EscalationListResponseSchema = z.array(EscalationListItemSchema)

export const EscalationActionSchema = z.enum(['accept', 'edit', 'reject'])
export type EscalationAction = z.infer<typeof EscalationActionSchema>

export const EscalationResolveRequestSchema = z.object({
  action: EscalationActionSchema,
  routing: z
    .object({
      queue: QueueSchema.optional(),
      priority: PrioritySchema.optional(),
      sla_minutes: z.number().int().positive().optional(),
      rationale: z.string().optional(),
    })
    .partial()
    .nullable()
    .optional(),
  reason: z.string().nullable().optional(),
  reviewer: z.string().default('anonymous'),
})
export type EscalationResolveRequest = z.infer<typeof EscalationResolveRequestSchema>

export const EscalationResolveResponseSchema = z.object({
  escalation_id: z.string().uuid(),
  ticket_id: z.string().uuid(),
  status: z.string(),
  resumed: z.boolean(),
})
export type EscalationResolveResponse = z.infer<typeof EscalationResolveResponseSchema>

export const HealthSchema = z.object({ status: z.string() })
export type Health = z.infer<typeof HealthSchema>

// ---------------------------------------------------------------------------
// Trigger reason parsing — backend emits things like "low_confidence=0.62"
// ---------------------------------------------------------------------------

export interface ParsedReason {
  kind: string
  value?: string
  raw: string
}

export function parseReason(raw: string): ParsedReason {
  const eq = raw.indexOf('=')
  if (eq === -1) return { kind: raw, raw }
  return { kind: raw.slice(0, eq), value: raw.slice(eq + 1), raw }
}
