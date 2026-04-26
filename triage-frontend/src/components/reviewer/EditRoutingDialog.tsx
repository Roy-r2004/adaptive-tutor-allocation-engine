import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  PrioritySchema,
  QueueSchema,
  type Priority,
  type Queue,
  type Routing,
} from '@/lib/schemas'

export interface EditRoutingValue {
  queue: Queue
  priority?: Priority
  sla_minutes?: number
  rationale?: string
}

interface Props {
  open: boolean
  onOpenChange(open: boolean): void
  initial?: Routing | null
  currentPriority?: Priority
  onSubmit(value: EditRoutingValue): void
}

const SLA_FOR_PRIORITY: Record<Priority, number> = {
  high: 15,
  medium: 60,
  low: 240,
}

export function EditRoutingDialog({
  open,
  onOpenChange,
  initial,
  currentPriority = 'medium',
  onSubmit,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {/*
          Form lives in a child so its useState defaults re-initialize whenever
          the dialog is opened. Radix unmounts DialogContent when `open=false`,
          so we don't need a useEffect to reset state — avoids the
          react-hooks/set-state-in-effect rule entirely.
        */}
        {open && (
          <EditRoutingForm
            initialQueue={initial?.queue ?? 'fallback'}
            initialPriority={currentPriority}
            onCancel={() => onOpenChange(false)}
            onSubmit={onSubmit}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function EditRoutingForm({
  initialQueue,
  initialPriority,
  onCancel,
  onSubmit,
}: {
  initialQueue: Queue
  initialPriority: Priority
  onCancel(): void
  onSubmit(v: EditRoutingValue): void
}) {
  const [queue, setQueue] = useState<Queue>(initialQueue)
  const [priority, setPriority] = useState<Priority>(initialPriority)
  const [rationale, setRationale] = useState('')

  const submit = () => {
    onSubmit({
      queue,
      priority,
      sla_minutes: SLA_FOR_PRIORITY[priority],
      rationale: rationale.trim() || undefined,
    })
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Override routing</DialogTitle>
        <DialogDescription>
          Pick the queue and priority a human-on-call should pick this up with. Changing priority
          adjusts SLA automatically.
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-4 mt-2">
        <div className="grid gap-1.5">
          <Label htmlFor="queue">Queue</Label>
          <Select value={queue} onValueChange={(v) => setQueue(v as Queue)}>
            <SelectTrigger id="queue">
              <SelectValue placeholder="Choose queue" />
            </SelectTrigger>
            <SelectContent>
              {QueueSchema.options.map((q) => (
                <SelectItem key={q} value={q}>
                  <span className="font-mono text-[13px]">{q}</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="priority">Priority</Label>
          <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
            <SelectTrigger id="priority">
              <SelectValue placeholder="Choose priority" />
            </SelectTrigger>
            <SelectContent>
              {PrioritySchema.options.map((p) => (
                <SelectItem key={p} value={p}>
                  <span className="capitalize">{p}</span>
                  <span className="ml-2 text-text-muted font-mono text-[11px]">
                    SLA {SLA_FOR_PRIORITY[p]}m
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-1.5">
          <Label htmlFor="rationale">Rationale</Label>
          <Textarea
            id="rationale"
            rows={3}
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            placeholder="Why is this override correct? (logged with the resolution)"
          />
        </div>
      </div>

      <DialogFooter className="mt-4">
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="primary" onClick={submit}>
          Save & resume
        </Button>
      </DialogFooter>
    </>
  )
}
