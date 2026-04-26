import { useMemo, useRef, useState, useEffect } from 'react'
import { toast } from 'sonner'
import { ChatComposer, type ChatComposerHandle } from '@/components/chat/ChatComposer'
import { ChatThread, type ChatTurn } from '@/components/chat/ChatThread'
import { Sidebar, type ConversationStub } from '@/components/chat/Sidebar'
import { useIngestMessage } from '@/lib/queries'
import { ApiHttpError } from '@/lib/api'

type ConvoMap = Record<string, ChatTurn[]>

function uid(): string {
  return globalThis.crypto?.randomUUID?.() ?? `c_${Date.now()}_${Math.random().toString(36).slice(2)}`
}

export function Chat() {
  const [conversations, setConversations] = useState<ConversationStub[]>(() => {
    const id = uid()
    return [{ id, title: 'New conversation', startedAt: Date.now() }]
  })
  const [activeId, setActiveId] = useState<string>(() => conversations[0]!.id)
  const [turnsByConvo, setTurnsByConvo] = useState<ConvoMap>({ [conversations[0]!.id]: [] })

  const ingest = useIngestMessage()
  const composerRef = useRef<ChatComposerHandle | null>(null)

  useEffect(() => {
    composerRef.current?.focus()
  }, [activeId])

  const turns = useMemo(() => turnsByConvo[activeId] ?? [], [turnsByConvo, activeId])

  const handleSend = (text: string) => {
    const userTurn: ChatTurn = {
      id: uid(),
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    setTurnsByConvo((m) => ({ ...m, [activeId]: [...(m[activeId] ?? []), userTurn] }))

    setConversations((cs) =>
      cs.map((c) =>
        c.id === activeId
          ? { ...c, title: c.title === 'New conversation' ? truncate(text, 48) : c.title }
          : c,
      ),
    )

    ingest.mutate(
      { source: 'chat', body: text, tenant_id: 'default', extra: {} },
      {
        onSuccess: (res) => {
          const sysTurn: ChatTurn = {
            id: uid(),
            role: 'system',
            content:
              "Got it — running this through triage now. You'll see live updates below as it moves through the pipeline.",
            ticketId: res.ticket_id,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          }
          setTurnsByConvo((m) => ({ ...m, [activeId]: [...(m[activeId] ?? []), sysTurn] }))
          setConversations((cs) =>
            cs.map((c) => (c.id === activeId ? { ...c, ticketId: res.ticket_id } : c)),
          )
        },
        onError: (err) => {
          const msg = err instanceof ApiHttpError ? err.message : (err as Error).message
          toast.error('Failed to submit ticket', { description: msg })
        },
      },
    )
  }

  const handleNew = () => {
    const id = uid()
    setConversations((cs) => [{ id, title: 'New conversation', startedAt: Date.now() }, ...cs])
    setTurnsByConvo((m) => ({ ...m, [id]: [] }))
    setActiveId(id)
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg">
      {/* Sidebar — hidden on mobile, shown on >= md */}
      <div className="hidden md:flex md:w-[300px] lg:w-[320px] shrink-0">
        <Sidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={setActiveId}
          onNew={handleNew}
        />
      </div>

      {/* Main pane */}
      <main className="flex-1 flex flex-col min-w-0">
        <MobileTopBar onNew={handleNew} />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 sm:px-6 py-8">
            <ChatThread turns={turns} />
          </div>
        </div>
        <div className="border-t border-border bg-bg-subtle/40">
          <div className="mx-auto w-full max-w-3xl px-4 sm:px-6 py-4">
            <ChatComposer
              ref={composerRef}
              onSend={handleSend}
              pending={ingest.isPending}
              placeholder="Describe what's happening — be specific about what you tried and what you saw."
            />
          </div>
        </div>
      </main>
    </div>
  )
}

function MobileTopBar({ onNew }: { onNew: () => void }) {
  return (
    <div className="md:hidden flex items-center justify-between border-b border-border px-4 py-3 bg-bg-subtle/60">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded bg-accent text-white text-[11px] font-bold">
          A
        </span>
        <span className="text-[13px] font-semibold tracking-tightish">Apex AI Triage</span>
      </div>
      <button
        onClick={onNew}
        className="text-[12px] text-accent font-medium hover:underline underline-offset-2"
      >
        New
      </button>
    </div>
  )
}

function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s
}
