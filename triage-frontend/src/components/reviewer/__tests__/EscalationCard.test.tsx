import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { EscalationCard } from '@/components/reviewer/EscalationCard'
import type { EscalationListItem } from '@/lib/schemas'

const FIXTURE: EscalationListItem = {
  escalation_id: '00000000-0000-4000-8000-000000000001',
  ticket_id: '00000000-0000-4000-8000-0000000000aa',
  status: 'pending',
  reasons: ['low_confidence=0.62', 'keyword_match=outage'],
  payload: {
    classification: {
      category: 'incident_outage',
      priority: 'high',
      confidence: 0.62,
      rationale: 'mentions outage',
    },
    routing: {
      queue: 'engineering',
      sla_minutes: 15,
      rationale: 'incident → eng',
      decided_by: 'auto',
      needs_human: true,
    },
    body: 'The platform is down for all users right now.',
  },
  created_at: new Date().toISOString(),
}

function renderCard(onResolve = vi.fn()) {
  return {
    onResolve,
    ...render(
      <MemoryRouter>
        <EscalationCard escalation={FIXTURE} onResolve={onResolve} />
      </MemoryRouter>,
    ),
  }
}

describe('EscalationCard', () => {
  it('renders the trigger reasons as readable chips', () => {
    renderCard()
    // Use the human-formatted chip strings (which include the parsed value) so
    // we don't collide with text like the "Incident · outage" category badge.
    expect(screen.getByText(/low confidence · 0\.62/i)).toBeInTheDocument()
    expect(screen.getByText(/keyword · outage/i)).toBeInTheDocument()
  })

  it('renders the auto-proposed classification + queue', () => {
    renderCard()
    expect(screen.getByText(/Incident · outage/i)).toBeInTheDocument()
    expect(screen.getByText('engineering')).toBeInTheDocument()
  })

  it('Accept button triggers a resolve mutation with action=accept', async () => {
    const { onResolve } = renderCard()
    await userEvent.click(screen.getByTestId('action-accept'))
    expect(onResolve).toHaveBeenCalledTimes(1)
    expect(onResolve).toHaveBeenCalledWith({
      id: FIXTURE.escalation_id,
      payload: expect.objectContaining({ action: 'accept' }),
    })
  })

  it('Reject requires a reason before firing', async () => {
    const { onResolve } = renderCard()
    await userEvent.click(screen.getByTestId('action-reject'))
    const confirmBtn = screen.getByTestId('action-reject-confirm')
    expect(confirmBtn).toBeDisabled()
    const input = screen.getByPlaceholderText(/why are we rejecting/i)
    await userEvent.type(input, 'duplicate')
    expect(confirmBtn).not.toBeDisabled()
    await userEvent.click(confirmBtn)
    expect(onResolve).toHaveBeenCalledWith({
      id: FIXTURE.escalation_id,
      payload: expect.objectContaining({ action: 'reject', reason: 'duplicate' }),
    })
  })
})
