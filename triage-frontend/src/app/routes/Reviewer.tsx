import { ArrowLeft, Monitor, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { EscalationList } from '@/components/reviewer/EscalationList'
import { usePendingEscalations } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function Reviewer() {
  const { data, refetch, isRefetching } = usePendingEscalations()

  return (
    <>
      <DesktopOnlyGate />
      <div className="hidden md:flex flex-col min-h-screen bg-bg">
        <header className="border-b border-border bg-bg-subtle/40">
          <div className="mx-auto w-full max-w-5xl px-6 py-5 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Link
                to="/"
                className="inline-flex items-center gap-1.5 text-[12.5px] text-text-muted hover:text-text"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Chat
              </Link>
              <span className="text-text-muted">/</span>
              <h1 className="text-[20px] font-semibold tracking-tightish">Pending Escalations</h1>
              <Badge variant="muted" className="font-mono">
                {data?.length ?? 0}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-text-muted font-mono hidden sm:inline">
                auto-refresh · 5s
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => refetch()}
                disabled={isRefetching}
              >
                <RefreshCw className={cn('h-3.5 w-3.5', isRefetching && 'animate-spin')} />
                Refresh
              </Button>
            </div>
          </div>
        </header>

        <main className="flex-1">
          <div className="mx-auto w-full max-w-5xl px-6 py-7">
            <EscalationList />
          </div>
        </main>
      </div>
    </>
  )
}

function DesktopOnlyGate() {
  return (
    <div className="md:hidden flex flex-col min-h-screen items-center justify-center px-6 text-center bg-bg">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-bg-subtle mb-4 text-text-muted">
        <Monitor className="h-5 w-5" />
      </div>
      <h2 className="text-base font-semibold tracking-tightish">Use desktop</h2>
      <p className="mt-1 text-sm text-text-muted text-balance max-w-xs">
        The reviewer dashboard is desktop-only. Open this page on a screen at least 768 px wide.
      </p>
      <Link to="/" className="mt-5 text-[13px] text-accent font-medium hover:underline underline-offset-2">
        ← Back to chat
      </Link>
    </div>
  )
}
