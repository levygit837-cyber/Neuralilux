'use client'

import { useState, useRef, useCallback } from 'react'
import { Paperclip, Smile, Send } from 'lucide-react'

interface AgentInputBarProps {
  onSendMessage: (content: string) => void
  disabled?: boolean
}

export function AgentInputBar({ onSendMessage, disabled }: AgentInputBarProps) {
  const [message, setMessage] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (message.trim() && !disabled) {
        onSendMessage(message.trim())
        setMessage('')
        inputRef.current?.focus()
      }
    },
    [message, disabled, onSendMessage]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit(e)
      }
    },
    [handleSubmit]
  )

  return (
    <div className="border-t border-border-color bg-card px-6 py-4">
      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        {/* Attach Button */}
        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-text-muted hover:bg-hover hover:text-text-light"
        >
          <Paperclip className="h-5 w-5" />
        </button>

        {/* Input Field */}
        <div className="flex-1">
          <input
            ref={inputRef}
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Digite sua mensagem..."
            disabled={disabled}
            className="w-full rounded-full border border-border-color bg-dark px-4 py-3 text-sm text-text-light placeholder-text-muted focus:border-primary focus:bg-dark focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
          />
        </div>

        {/* Emoji Button */}
        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-lg text-text-muted hover:bg-hover hover:text-text-light"
        >
          <Smile className="h-5 w-5" />
        </button>

        {/* Send Button */}
        <button
          type="submit"
          disabled={!message.trim() || disabled}
          className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-white transition-colors hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send className="h-5 w-5" />
        </button>
      </form>
    </div>
  )
}