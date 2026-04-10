'use client'

import { useState, useRef, useCallback } from 'react'
import { Paperclip, Smile, Send } from 'lucide-react'

interface AgentInputBarProps {
  onSendMessage: (content: string) => void
  disabled?: boolean
}

export function AgentInputBar({ onSendMessage, disabled }: AgentInputBarProps) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resetTextarea = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()
      if (message.trim() && !disabled) {
        onSendMessage(message.trim())
        setMessage('')
        resetTextarea()
        textareaRef.current?.focus()
      }
    },
    [message, disabled, onSendMessage, resetTextarea]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSubmit(e)
      }
    },
    [handleSubmit]
  )

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [])

  return (
    <div className="absolute bottom-0 w-full left-0 bg-gradient-to-t from-dark via-dark to-transparent pt-12 pb-6 px-6 md:px-8 z-20 pointer-events-none">
      <div className="max-w-4xl mx-auto w-full pointer-events-auto">
        {/* Glassmorphic input wrapper */}
        <form
          onSubmit={handleSubmit}
          className="bg-[#1A1333]/90 backdrop-blur-md border border-border-color rounded-2xl flex items-end p-2 pb-2.5 shadow-2xl focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20 transition-all duration-300"
        >
          {/* Attachment button */}
          <button
            type="button"
            className="p-2.5 text-text-muted hover:text-text-light hover:bg-hover rounded-xl transition-colors mb-0.5"
            tabIndex={-1}
          >
            <Paperclip className="w-5 h-5" />
          </button>

          {/* Auto-grow textarea */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={message}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Interaja com o Agente IA (comandos, debug ou teste natural)..."
            disabled={disabled}
            className="bg-transparent text-[15px] text-text-light placeholder-text-muted resize-none outline-none flex-1 max-h-32 min-h-[44px] py-3 px-3 leading-tight block w-full rounded-md disabled:opacity-50"
          />

          <div className="flex items-center gap-1 mb-0.5">
            {/* Emoji button */}
            <button
              type="button"
              className="p-2.5 text-text-muted hover:text-text-light hover:bg-hover rounded-xl transition-colors"
              tabIndex={-1}
            >
              <Smile className="w-5 h-5" />
            </button>

            {/* Send button — gradient matching the reference design */}
            <button
              type="submit"
              disabled={!message.trim() || disabled}
              className="p-2.5 ml-1 bg-gradient-to-br from-primary-dark to-accent hover:from-primary hover:to-accent text-white rounded-xl shadow-[0_0_15px_rgba(139,92,246,0.4)] transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </form>

        {/* Footer disclaimer */}
        <div className="flex justify-center mt-3">
          <p className="text-[11px] text-text-muted flex items-center gap-2 font-medium">
            <svg className="w-3.5 h-3.5 text-success shrink-0" fill="currentColor" viewBox="0 0 256 256">
              <path d="M208,40H48A16,16,0,0,0,32,56V200a16,16,0,0,0,16,16H208a16,16,0,0,0,16-16V56A16,16,0,0,0,208,40ZM80,168a8,8,0,0,1,0-16h64a8,8,0,0,1,0,16Zm88-40H88a8,8,0,0,1,0-16h80a8,8,0,0,1,0,16ZM80,96H176a8,8,0,0,1,0,16H80a8,8,0,0,1,0-16Z" />
            </svg>
            O agente tem acesso seguro às ferramentas configuradas no workspace.
          </p>
        </div>
      </div>
    </div>
  )
}
