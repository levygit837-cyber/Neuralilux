import { useState } from 'react'
import { Paperclip, Smiley, Microphone, ArrowUp, Keyboard } from '@phosphor-icons/react'

interface ChatInputProps {
  onSendMessage: (content: string) => void
  disabled?: boolean
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('')

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const content = message.trim()
      if (content) {
        onSendMessage(content)
        setMessage('')
      }
    }
  }

  const handleSend = () => {
    const content = message.trim()
    if (content) {
      onSendMessage(content)
      setMessage('')
    }
  }

  return (
    <div className="border-t border-brand-border/50 bg-brand-card/80 backdrop-blur-sm px-3 sm:px-6 py-4">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <button
          type="button"
          aria-label="Anexar arquivo"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-base text-content-gray transition-colors hover:text-primary-light border border-brand-border hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Paperclip weight="regular" className="text-lg" aria-hidden="true" />
        </button>
        
        <div className="flex-1 relative">
          <textarea
            aria-label="Mensagem"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Digite sua mensagem..."
            disabled={disabled}
            onKeyDown={handleKeyDown}
            rows={1}
            className="w-full rounded-2xl border border-brand-border/80 bg-brand-base px-4 py-3 text-sm text-content-light placeholder-content-muted outline-none focus:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary transition-all resize-none shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px] max-h-[120px]"
            style={{ fieldSizing: 'content' }}
          />
          <div className="absolute bottom-2 right-2 text-[10px] text-content-muted opacity-0 hover:opacity-100 transition-opacity flex items-center gap-1 bg-brand-base/80 px-2 py-1 rounded">
            <Keyboard weight="regular" className="text-xs" aria-hidden="true" />
            Enter para enviar, Shift+Enter para nova linha
          </div>
        </div>

        <button
          type="button"
          aria-label="Inserir emoji"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-base text-content-gray transition-colors hover:text-primary-light border border-brand-border hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Smiley weight="regular" className="text-lg" aria-hidden="true" />
        </button>
        <button
          type="button"
          aria-label="Gravar áudio"
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-base text-content-gray transition-colors hover:text-primary-light border border-brand-border hover:border-primary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Microphone weight="regular" className="text-lg" aria-hidden="true" />
        </button>
        <button
          type="button"
          aria-label="Enviar mensagem"
          onClick={handleSend}
          disabled={!message.trim() || disabled}
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark text-white transition-all hover:shadow-glow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:from-brand-base disabled:to-brand-base disabled:text-content-muted"
        >
          <ArrowUp weight="bold" className="text-lg" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
