import { Building2, Code2, DollarSign, ShieldAlert, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Queue } from '@/lib/schemas'

interface Props {
  queue: Queue
  className?: string
}

const QUEUE_META: Record<Queue, { label: string; icon: typeof Code2 }> = {
  engineering: { label: 'engineering', icon: Code2 },
  billing: { label: 'billing', icon: DollarSign },
  product: { label: 'product', icon: Sparkles },
  it_security: { label: 'it_security', icon: ShieldAlert },
  fallback: { label: 'fallback', icon: Building2 },
}

export function QueuePill({ queue, className }: Props) {
  const m = QUEUE_META[queue]
  const Icon = m.icon
  return (
    <Badge variant="muted" className={className}>
      <Icon className="h-3 w-3" />
      <span className="font-mono text-[11px]">{m.label}</span>
    </Badge>
  )
}
