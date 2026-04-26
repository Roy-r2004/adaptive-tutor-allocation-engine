/**
 * Single axios instance + typed clients for the triage backend.
 * Every response is validated through Zod. Schema mismatches throw a typed
 * `ApiSchemaError` so the UI can surface useful messages instead of crashing
 * on undefined fields.
 */
import axios, { type AxiosError, type AxiosInstance, type AxiosResponse } from 'axios'
import type { ZodSchema } from 'zod'
import {
  EscalationListResponseSchema,
  EscalationResolveResponseSchema,
  HealthSchema,
  IngestRequestSchema,
  IngestResponseSchema,
  TicketStatusResponseSchema,
  type EscalationListItem,
  type EscalationResolveRequest,
  type EscalationResolveResponse,
  type IngestRequest,
  type IngestResponse,
  type TicketStatusResponse,
} from '@/lib/schemas'

export class ApiSchemaError extends Error {
  readonly issues: unknown
  constructor(message: string, issues: unknown) {
    super(message)
    this.name = 'ApiSchemaError'
    this.issues = issues
  }
}

export class ApiHttpError extends Error {
  readonly status: number
  readonly detail: unknown
  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiHttpError'
    this.status = status
    this.detail = detail
  }
}

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const apiKey = import.meta.env.VITE_API_KEY ?? ''

export const api: AxiosInstance = axios.create({
  baseURL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  if (apiKey) {
    config.headers.set?.('X-API-Key', apiKey)
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ detail?: unknown }>) => {
    if (err.response) {
      const detail = err.response.data?.detail ?? err.response.data ?? err.message
      const msg =
        typeof detail === 'string' ? detail : `HTTP ${err.response.status} ${err.response.statusText}`
      return Promise.reject(new ApiHttpError(err.response.status, msg, detail))
    }
    return Promise.reject(new ApiHttpError(0, err.message ?? 'Network error'))
  },
)

/**
 * Validate a payload against a Zod schema. Public so tests can exercise it
 * directly without a real HTTP roundtrip.
 */
export function validate<T>(schema: ZodSchema<T>, data: unknown, label: string): T {
  const parsed = schema.safeParse(data)
  if (!parsed.success) {
    throw new ApiSchemaError(`Invalid ${label} response shape`, parsed.error.issues)
  }
  return parsed.data
}

function unwrap<T>(schema: ZodSchema<T>, label: string) {
  return (res: AxiosResponse): T => validate(schema, res.data, label)
}

// ---------------------------------------------------------------------------
// Typed clients
// ---------------------------------------------------------------------------

export async function ingestMessage(input: IngestRequest): Promise<IngestResponse> {
  const body = IngestRequestSchema.parse(input)
  return api.post('/v1/webhook/ingest', body).then(unwrap(IngestResponseSchema, 'ingest'))
}

export async function getTicket(id: string): Promise<TicketStatusResponse> {
  return api.get(`/v1/tickets/${id}`).then(unwrap(TicketStatusResponseSchema, 'ticket'))
}

export async function listEscalations(): Promise<EscalationListItem[]> {
  return api.get('/v1/escalations').then(unwrap(EscalationListResponseSchema, 'escalations'))
}

export async function resolveEscalation(
  id: string,
  payload: EscalationResolveRequest,
): Promise<EscalationResolveResponse> {
  return api
    .post(`/v1/escalations/${id}/resolve`, payload)
    .then(unwrap(EscalationResolveResponseSchema, 'escalation:resolve'))
}

export async function getHealth(): Promise<{ status: string }> {
  return api.get('/healthz').then(unwrap(HealthSchema, 'health'))
}
