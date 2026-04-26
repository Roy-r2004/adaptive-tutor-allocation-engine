import { Toaster as Sonner } from 'sonner'

export function Toaster() {
  return (
    <Sonner
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            'group toast bg-surface border border-border text-text shadow-lg shadow-black/5 rounded-lg',
          description: 'text-text-muted text-sm',
          actionButton: 'bg-accent text-white',
          cancelButton: 'bg-bg-subtle text-text',
        },
      }}
    />
  )
}
