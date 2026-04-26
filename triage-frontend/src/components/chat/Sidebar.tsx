import { Link, NavLink } from 'react-router-dom'
import { Activity, MessageSquarePlus, Triangle, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { shortId } from '@/lib/format'
import { useHealth } from '@/lib/queries'

export interface ConversationStub {
  id: string
  title: string
  ticketId?: string
  startedAt: number
}

interface Props {
  conversations: ConversationStub[]
  activeId: string | null
  onSelect(id: string): void
  onNew(): void
  className?: string
}

export function Sidebar({ conversations, activeId, onSelect, onNew, className }: Props) {
  const env = (import.meta.env.VITE_ENV as string | undefined) ?? 'dev'
  const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'
  const { data: health, error } = useHealth()

  return (
    <aside
      className={cn(
        'flex flex-col h-full w-full border-r border-border bg-bg-subtle/60',
        'backdrop-blur-sm',
        className,
      )}
    >
      <div className="flex items-center gap-2.5 px-5 pt-5 pb-4">
        <Link to="/" className="flex items-center gap-2.5 group">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent shadow-sm shadow-accent/30">
            <Triangle className="h-3.5 w-3.5 text-white" fill="currentColor" />
          </span>
          <div className="flex flex-col leading-none">
            <span className="text-[13px] font-semibold tracking-tightish">Apex AI Triage</span>
            <span className="text-[11px] text-text-muted">support intake</span>
          </div>
        </Link>
      </div>

      <div className="px-3 pb-3">
        <Button variant="secondary" size="md" className="w-full justify-start" onClick={onNew}>
          <MessageSquarePlus className="h-4 w-4" />
          New conversation
        </Button>
      </div>

      <div className="px-5 pt-2 pb-1.5 text-[11px] font-medium uppercase tracking-wider text-text-muted">
        History
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
        {conversations.length === 0 ? (
          <p className="px-3 py-2 text-xs text-text-muted">
            No conversations yet. Send a message to start one.
          </p>
        ) : (
          conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={cn(
                'group flex w-full items-start gap-2 rounded-md px-3 py-2 text-left transition-colors',
                activeId === c.id
                  ? 'bg-surface text-text border border-border shadow-sm'
                  : 'text-text-muted hover:bg-surface hover:text-text border border-transparent',
              )}
            >
              <div className="flex-1 min-w-0">
                <div className="truncate text-[13px] font-medium leading-tight">
                  {c.title || 'Untitled'}
                </div>
                {c.ticketId && (
                  <div className="mt-0.5 font-mono text-[10.5px] text-text-muted">
                    {shortId(c.ticketId)}
                  </div>
                )}
              </div>
            </button>
          ))
        )}
      </nav>

      <div className="mt-auto border-t border-border px-4 py-3 space-y-2.5">
        <NavLink
          to="/reviewer"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 rounded-md px-2.5 py-1.5 text-[13px] transition-colors',
              isActive
                ? 'bg-surface text-text border border-border'
                : 'text-text-muted hover:text-text hover:bg-surface',
            )
          }
        >
          <ShieldCheck className="h-4 w-4" />
          Reviewer dashboard
        </NavLink>

        <div className="flex items-center justify-between text-[11px]">
          <div className="flex items-center gap-1.5 text-text-muted">
            <Activity
              className={cn(
                'h-3 w-3',
                error ? 'text-danger' : health ? 'text-success' : 'text-text-muted',
              )}
            />
            <span className="font-mono lowercase">{env}</span>
          </div>
          <span className="font-mono text-text-muted truncate max-w-[55%]" title={baseUrl}>
            {baseUrl.replace(/^https?:\/\//, '')}
          </span>
        </div>
      </div>
    </aside>
  )
}
