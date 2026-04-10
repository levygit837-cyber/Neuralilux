import { ChatCircleDots } from '@phosphor-icons/react'

export function EmptyChat() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-brand-card border border-brand-border">
        <ChatCircleDots weight="regular" className="text-4xl text-content-muted" />
      </div>
      <div>
        <h3 className="text-lg font-semibold text-content-light">Selecione uma conversa</h3>
        <p className="text-sm text-content-muted">Escolha uma conversa da lista para começar</p>
      </div>
    </div>
  )
}
