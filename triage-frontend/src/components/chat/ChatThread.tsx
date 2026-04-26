import { useEffect, useRef } from 'react'
import { Sparkles } from 'lucide-react'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { TicketStatusCard } from '@/components/chat/TicketStatusCard'
import { cn } from '@/lib/utils'

export interface ChatTurn {
  id: string
  role: 'user' | 'system'
  content: string
  ticketId?: string
  timestamp: string
}

interface Props {
  turns: ChatTurn[]
  className?: string
}

export function ChatThread({ turns, className }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns.length])

  if (turns.length === 0) {
    return <EmptyHero className={className} />
  }

  return (
    <div className={cn('flex flex-col gap-5 px-1', className)}>
      {turns.map((t) => (
        <div key={t.id} className="space-y-3">
          <MessageBubble role={t.role} content={t.content} timestamp={t.timestamp} />
          {t.ticketId && <TicketStatusCard ticketId={t.ticketId} />}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  )
}

function EmptyHero({ className }: { className?: string }) {
  return (
    <div className={cn('flex flex-col h-full justify-center items-start max-w-2xl', className)}>
      <div className="mb-5 flex h-9 w-9 items-center justify-center rounded-md border border-accent/20 bg-accent/10 text-accent">
        <Sparkles className="h-4 w-4" />
      </div>
      <h1 className="text-[28px] font-semibold tracking-tightish leading-tight text-balance">
        Tell us what&apos;s going on.
      </h1>
      <p className="mt-2 text-[15px] text-text-muted leading-relaxed text-balance">
        We&apos;ll classify your issue, route it to the right team, and escalate to a human if it
        looks urgent. Average response time is under 5 minutes during business hours.
      </p>
      <div className="mt-6 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <span
            key={s}
            className="rounded-full border border-border bg-surface px-3 py-1.5 text-[12.5px] text-text-muted"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}

const SUGGESTIONS = [
  'I was charged twice for my subscription',
  'The video player keeps buffering on every lesson',
  'Can we add export-to-CSV for tutor reports?',
  'The platform is down for all users',
]
