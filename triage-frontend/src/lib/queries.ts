import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getHealth,
  getTicket,
  ingestMessage,
  listEscalations,
  resolveEscalation,
} from '@/lib/api'
import type {
  EscalationListItem,
  EscalationResolveRequest,
  IngestRequest,
  TicketStatusResponse,
} from '@/lib/schemas'

export const ticketKeys = {
  all: ['tickets'] as const,
  detail: (id: string) => ['tickets', id] as const,
}

export const escalationKeys = {
  all: ['escalations'] as const,
}

const TERMINAL_STATUSES = new Set(['resolved', 'awaiting_review'])

/**
 * Live ticket polling. Polls every 1s while the ticket is still being
 * processed; halts once the backend reports a terminal state.
 */
export function useTicket(id: string | undefined) {
  return useQuery<TicketStatusResponse>({
    queryKey: ticketKeys.detail(id ?? '__none__'),
    queryFn: () => getTicket(id as string),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as TicketStatusResponse | undefined
      if (!data) return 1000
      return TERMINAL_STATUSES.has(data.status) ? false : 1000
    },
    refetchOnWindowFocus: false,
  })
}

export function usePendingEscalations() {
  return useQuery<EscalationListItem[]>({
    queryKey: escalationKeys.all,
    queryFn: listEscalations,
    refetchInterval: 5000,
    refetchOnWindowFocus: true,
  })
}

/**
 * Pulls the (single, currently-pending) escalation matching a given ticket id
 * out of the cached escalations list — used so the chat surface can show real
 * trigger reasons + proposed classification when a ticket is awaiting_review.
 */
export function useEscalationForTicket(ticketId: string | undefined) {
  const q = usePendingEscalations()
  const escalation = q.data?.find((e) => e.ticket_id === ticketId)
  return { ...q, escalation }
}

export function useIngestMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: IngestRequest) => ingestMessage(input),
    onSuccess: (res) => {
      // Pre-seed the ticket cache so the first poll is instant.
      qc.setQueryData(ticketKeys.detail(res.ticket_id), undefined)
    },
  })
}

interface ResolveVars {
  id: string
  payload: EscalationResolveRequest
}

export function useResolveEscalation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, payload }: ResolveVars) => resolveEscalation(id, payload),
    onMutate: async ({ id }) => {
      await qc.cancelQueries({ queryKey: escalationKeys.all })
      const prev = qc.getQueryData<EscalationListItem[]>(escalationKeys.all)
      qc.setQueryData<EscalationListItem[]>(escalationKeys.all, (rows) =>
        (rows ?? []).filter((r) => r.escalation_id !== id),
      )
      return { prev }
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(escalationKeys.all, ctx.prev)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: escalationKeys.all })
    },
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
    retry: 1,
  })
}
