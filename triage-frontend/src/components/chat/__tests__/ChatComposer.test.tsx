import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatComposer } from '@/components/chat/ChatComposer'

const getTextarea = () =>
  screen.getByRole('textbox', { name: /message/i }) as HTMLTextAreaElement

describe('ChatComposer', () => {
  it('does not call onSend when input is empty and Cmd+Enter is pressed', async () => {
    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} />)
    const ta = getTextarea()
    await userEvent.click(ta)
    await userEvent.keyboard('{Meta>}{Enter}{/Meta}')
    expect(onSend).not.toHaveBeenCalled()
    expect(screen.getByTestId('composer-send')).toBeDisabled()
  })

  it('calls onSend with trimmed text when Cmd+Enter is pressed', async () => {
    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} />)
    const ta = getTextarea()
    await userEvent.type(ta, '   hello world   ')
    await userEvent.keyboard('{Meta>}{Enter}{/Meta}')
    expect(onSend).toHaveBeenCalledTimes(1)
    expect(onSend).toHaveBeenCalledWith('hello world')
  })

  it('calls onSend when Ctrl+Enter is pressed (non-Mac)', async () => {
    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} />)
    const ta = getTextarea()
    await userEvent.type(ta, 'ping')
    await userEvent.keyboard('{Control>}{Enter}{/Control}')
    expect(onSend).toHaveBeenCalledWith('ping')
  })

  it('inserts a newline on plain Enter (does not send)', async () => {
    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} />)
    const ta = getTextarea()
    await userEvent.type(ta, 'line one{Enter}line two')
    expect(onSend).not.toHaveBeenCalled()
    expect(ta.value).toContain('\n')
  })

  it('sends via the send button click', async () => {
    const onSend = vi.fn()
    render(<ChatComposer onSend={onSend} />)
    await userEvent.type(getTextarea(), 'click me')
    await userEvent.click(screen.getByTestId('composer-send'))
    expect(onSend).toHaveBeenCalledWith('click me')
  })

  it('disables send while pending', () => {
    render(<ChatComposer onSend={vi.fn()} pending />)
    expect(screen.getByTestId('composer-send')).toBeDisabled()
  })
})
