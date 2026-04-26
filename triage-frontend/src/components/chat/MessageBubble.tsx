import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

export type MessageRole = 'user' | 'system'

interface Props {
  role: MessageRole
  content: string
  timestamp?: string
}

export function MessageBubble({ role, content, timestamp }: Props) {
  const isUser = role === 'user'
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}
    >
      {!isUser && (
        <div className="mr-2.5 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-bg-subtle text-text-muted">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
      )}
      <div className={cn('flex max-w-[78%] flex-col', isUser ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'rounded-lg px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap',
            isUser
              ? 'bg-accent/10 text-text border border-accent/20'
              : 'bg-surface text-text border border-border',
          )}
        >
          {content}
        </div>
        {timestamp && (
          <span className="mt-1 px-0.5 font-mono text-[10.5px] text-text-muted">{timestamp}</span>
        )}
      </div>
    </motion.div>
  )
}
