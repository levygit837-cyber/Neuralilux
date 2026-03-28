'use client'

import type { ReactNode } from 'react'
import { AlertTriangle, Clock3, FileInput, FileOutput, Info } from 'lucide-react'
import type { AgentToolEvent } from '@/types/agent'

interface ToolResultCardProps {
  toolEvent: AgentToolEvent
}

function formatTimestamp(value?: string): string | null {
  if (!value) {
    return null
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }

  return parsed.toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatPayload(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === 'string') {
    const normalized = value.trim()
    return normalized || null
  }

  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function DetailSection({
  title,
  content,
  tone,
  icon,
}: {
  title: string
  content: string
  tone: 'default' | 'error'
  icon: ReactNode
}) {
  return (
    <div
      className={`rounded-2xl border px-3 py-3 ${
        tone === 'error'
          ? 'border-red-500/20 bg-red-500/5'
          : 'border-white/10 bg-[#120F27]/80'
      }`}
    >
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#B9B1DD]">
        {icon}
        <span>{title}</span>
      </div>
      <pre className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-black/20 px-3 py-2 text-xs leading-6 text-text-gray">
        {content}
      </pre>
    </div>
  )
}

export function ToolResultCard({ toolEvent }: ToolResultCardProps) {
  const inputContent = formatPayload(toolEvent.inputPayload ?? toolEvent.inputPreview)
  const outputContent = formatPayload(toolEvent.outputPayload ?? toolEvent.outputPreview)
  const errorContent = formatPayload(toolEvent.error)
  const startedAt = formatTimestamp(toolEvent.startedAt || toolEvent.persistedAt)
  const finishedAt = formatTimestamp(toolEvent.finishedAt)

  return (
    <div className="space-y-3">
      <div className="grid gap-3 lg:grid-cols-2">
        {inputContent && (
          <DetailSection
            title="Entrada"
            content={inputContent}
            tone="default"
            icon={<FileInput className="h-3.5 w-3.5" />}
          />
        )}

        {errorContent ? (
          <DetailSection
            title="Erro"
            content={errorContent}
            tone="error"
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
          />
        ) : outputContent ? (
          <DetailSection
            title="Resultado"
            content={outputContent}
            tone="default"
            icon={<FileOutput className="h-3.5 w-3.5" />}
          />
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2 text-[11px] text-[#A79DCC]">
        {startedAt && (
          <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
            <Clock3 className="h-3.5 w-3.5" />
            <span>Início {startedAt}</span>
          </span>
        )}
        {finishedAt && (
          <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
            <Clock3 className="h-3.5 w-3.5" />
            <span>Fim {finishedAt}</span>
          </span>
        )}
        {toolEvent.traceId && (
          <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
            <Info className="h-3.5 w-3.5" />
            <span>Trace {toolEvent.traceId.slice(0, 12)}</span>
          </span>
        )}
      </div>
    </div>
  )
}
