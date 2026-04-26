import { AlertTriangle, Bug, DollarSign, HelpCircle, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Category } from '@/lib/schemas'

interface Props {
  category: Category
  className?: string
}

const META: Record<
  Category,
  {
    label: string
    variant: 'danger-solid' | 'warning' | 'accent' | 'outline'
    icon: typeof Bug
  }
> = {
  incident_outage: { label: 'Incident · outage', variant: 'danger-solid', icon: AlertTriangle },
  bug_report: { label: 'Bug report', variant: 'warning', icon: Bug },
  billing_issue: { label: 'Billing', variant: 'warning', icon: DollarSign },
  feature_request: { label: 'Feature request', variant: 'accent', icon: Sparkles },
  technical_question: { label: 'Tech question', variant: 'outline', icon: HelpCircle },
}

export function CategoryBadge({ category, className }: Props) {
  const m = META[category]
  const Icon = m.icon
  return (
    <Badge variant={m.variant} className={className}>
      <Icon className="h-3 w-3" />
      <span>{m.label}</span>
    </Badge>
  )
}
