import { useState } from 'react'
import { Paperclip, Smiley, Microphone, ArrowUp, Keyboard } from '@phosphor-icons/react'

interface ChatInputProps {
  onSendMessage: (content: string) => void
  onTyping: (isTyping: boolean) => void
  disabled?: boolean
}

export function ChatInput({ onSendMessage, onTyping, disabled }: ChatInputProps) {
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

  const handleBlur = () => {
    onTyping(false)
  }

  const handleFocus = () => {
    onTyping(true)
  }

  const handleSend = () => {
    const content = message.trim()
    if (content) {
      onSendMessage(content)
      setMessage('')
    }
  }

  return (
    <div className="border-t border-brand-border/50 bg-brand-card/80 backdrop-blur-sm px-6 py-4">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <button className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-base text-content-gray transition-colors hover:text-primary border border-brand-border hover:border-primary/30">
          <Paperclip weight="regular" className="text-lg" />
        </button>
        
        <div className="flex-1 relative">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Digite sua mensagem..."
            disabled={disabled}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            onFocus={handleFocus}
            rows={1}
            className="w-full rounded-2xl border border-brand-border/80 bg-brand-base px-4 py-3 text-sm text-content-light placeholder-content-muted outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all resize-none shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)] disabled:cursor-not-allowed disabled:opacity-50 min-h-[44px] max-h-[120px]"
            style={{ fieldSizing: 'content' }}
          />
          <div className="absolute bottom-2 right-2 text-[10px] text-content-muted opacity-0 hover:opacity-100 transition-opacity flex items-center gap-1 bg-brand-base/80 px-2 py-1 rounded">
            <Keyboard weight="regular" className="text-xs" />
            Enter para enviar, Shift+Enter para nova linha
          </div>
        </div>

        <button className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-base text-content-gray transition-colors hover:text-primary border border-brand-border hover:border-primary/30">
          <Smiley weight="regular" className="text-lg" />
        </button>
        <button className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-brand-base text-content-gray transition-colors hover:text-primary border border-brand-border hover:border-primary/30">
          <Microphone weight="regular" className="text-lg" />
        </button>
        <button 
          onClick={handleSend}
          disabled={!message.trim() || disabled}
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary-dark text-white transition-all hover:shadow-glow disabled:opacity-50 disabled:cursor-not-allowed disabled:from-brand-base disabled:to-brand-base disabled:text-content-muted"
        >
          <ArrowUp weight="bold" className="text-lg" />
        </button>
      </div>
    </div>
  )
}
