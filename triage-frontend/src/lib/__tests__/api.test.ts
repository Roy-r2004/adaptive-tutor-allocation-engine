import { describe, expect, it } from 'vitest'
import { ApiSchemaError, validate } from '@/lib/api'
import {
  IngestResponseSchema,
  TicketStatusResponseSchema,
  EscalationListResponseSchema,
} from '@/lib/schemas'

describe('api / Zod validation', () => {
  it('accepts a valid IngestResponse', () => {
    const ok = validate(
      IngestResponseSchema,
      {
        message_id: '00000000-0000-4000-8000-000000000001',
        ticket_id: '00000000-0000-4000-8000-000000000002',
        job_id: 'triage:abc',
        status: 'queued',
      },
      'ingest',
    )
    expect(ok.job_id).toBe('triage:abc')
  })

  it('rejects an IngestResponse missing required fields', () => {
    expect(() =>
      validate(IngestResponseSchema, { ticket_id: 'not-a-uuid' }, 'ingest'),
    ).toThrowError(ApiSchemaError)
  })

  it('rejects a TicketStatusResponse with the wrong final_output shape', () => {
    expect(() =>
      validate(
        TicketStatusResponseSchema,
        {
          ticket_id: '00000000-0000-4000-8000-000000000002',
          status: 'resolved',
          has_pending_escalation: false,
          created_at: '2026-04-26T00:00:00Z',
          updated_at: '2026-04-26T00:00:00Z',
          final_output: {
            // Wrong: missing classification / enrichment / routing / escalation
            ticket_id: 'x',
            message_id: 'y',
            source: 'chat',
            received_at: '2026-04-26T00:00:00Z',
            human_summary: 'oops',
          },
        },
        'ticket',
      ),
    ).toThrowError(ApiSchemaError)
  })

  it('parses an empty escalation list', () => {
    const ok = validate(EscalationListResponseSchema, [], 'escalations')
    expect(ok).toEqual([])
  })

  it('rejects a category outside the literal enum', () => {
    expect(() =>
      validate(
        TicketStatusResponseSchema,
        {
          ticket_id: '00000000-0000-4000-8000-000000000002',
          status: 'resolved',
          has_pending_escalation: false,
          created_at: '2026-04-26T00:00:00Z',
          updated_at: '2026-04-26T00:00:00Z',
          final_output: {
            ticket_id: 'x',
            message_id: 'y',
            source: 'chat',
            received_at: '2026-04-26T00:00:00Z',
            classification: {
              category: 'sentient_takeover', // not one of the allowed literals
              priority: 'high',
              confidence: 0.9,
              rationale: 'r',
            },
            enrichment: { issue_summary: 's' },
            routing: { queue: 'engineering', sla_minutes: 15, rationale: 'r' },
            escalation: {},
            human_summary: 'h',
          },
        },
        'ticket',
      ),
    ).toThrowError(ApiSchemaError)
  })
})
