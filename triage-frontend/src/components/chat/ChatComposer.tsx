import { ArrowUp, Loader2 } from 'lucide-react'
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
} from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const MIN_ROWS = 1
const MAX_ROWS = 6
const LINE_HEIGHT_PX = 20 // matches text-sm leading
const VERTICAL_PADDING_PX = 16 // py-2 top + bottom

export interface ChatComposerHandle {
  focus(): void
}

interface Props {
  onSend(text: string): void
  pending?: boolean
  disabled?: boolean
  placeholder?: string
  className?: string
}

export const ChatComposer = forwardRef<ChatComposerHandle, Props>(
  ({ onSend, pending = false, disabled = false, placeholder, className }, ref) => {
    const [value, setValue] = useState('')
    const taRef = useRef<HTMLTextAreaElement | null>(null)

    useImperativeHandle(ref, () => ({
      focus: () => taRef.current?.focus(),
    }))

    const autosize = useCallback(() => {
      const ta = taRef.current
      if (!ta) return
      ta.style.height = 'auto'
      const maxH = MAX_ROWS * LINE_HEIGHT_PX + VERTICAL_PADDING_PX
      const minH = MIN_ROWS * LINE_HEIGHT_PX + VERTICAL_PADDING_PX
      const next = Math.min(maxH, Math.max(minH, ta.scrollHeight))
      ta.style.height = `${next}px`
    }, [])

    useEffect(() => {
      autosize()
    }, [value, autosize])

    const trimmed = value.trim()
    const canSend = !!trimmed && !pending && !disabled

    const submit = () => {
      if (!canSend) return
      onSend(trimmed)
      setValue('')
    }

    const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Cmd/Ctrl+Enter sends; plain Enter inserts a newline.
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        submit()
      }
    }

    return (
      <div
        className={cn(
          'rounded-lg border border-border bg-surface shadow-sm',
          'focus-within:border-border-strong focus-within:ring-2 focus-within:ring-accent/30',
          'transition-colors',
          className,
        )}
      >
        <Textarea
          ref={taRef}
          value={value}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          rows={MIN_ROWS}
          placeholder={placeholder ?? 'Describe the issue you ran into…'}
          aria-label="Message"
          disabled={disabled || pending}
          className="border-0 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 px-3.5 pt-3 pb-1.5 text-[14px] leading-5 max-h-[140px]"
        />
        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <div className="flex items-center gap-1.5 text-[11px] text-text-muted font-mono">
            <kbd className="rounded border border-border bg-bg-subtle px-1 py-px">⌘</kbd>
            <kbd className="rounded border border-border bg-bg-subtle px-1 py-px">↵</kbd>
            <span>to send</span>
          </div>
          <Button
            type="button"
            size="icon"
            variant="primary"
            onClick={submit}
            disabled={!canSend}
            aria-label="Send message"
            data-testid="composer-send"
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    )
  },
)
ChatComposer.displayName = 'ChatComposer'
