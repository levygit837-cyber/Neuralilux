import { useState } from 'react'
import { Paperclip, Send } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface ChatInputProps {
  onSendMessage: (message: string) => void
  disabled?: boolean
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim() && !disabled) {
      onSendMessage(message.trim())
      setMessage('')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-3 border-t border-border-color bg-card p-6">
      <button
        type="button"
        className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover text-text-gray transition-colors hover:bg-border"
      >
        <Paperclip className="h-5 w-5" />
      </button>
      <input
        type="text"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="Digite uma mensagem..."
        disabled={disabled}
        className="flex-1 rounded-md border-none bg-dark px-4 py-3 text-sm text-text-light placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
      />
      <Button
        type="submit"
        disabled={!message.trim() || disabled}
        className="h-12 w-12 rounded-full p-0"
      >
        <Send className="h-5 w-5" />
      </Button>
    </form>
  )
}
