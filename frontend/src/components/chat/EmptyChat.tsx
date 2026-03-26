import { MessageSquare } from 'lucide-react'

export function EmptyChat() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-card">
        <MessageSquare className="h-10 w-10 text-text-muted" />
      </div>
      <div>
        <h3 className="text-lg font-semibold text-text-light">Selecione uma conversa</h3>
        <p className="text-sm text-text-muted">Escolha uma conversa da lista para começar</p>
      </div>
    </div>
  )
}
