'use client'

import { useState } from 'react'
import type { ComponentType } from 'react'
import {
  CheckCircle2,
  ChevronDown,
  Database,
  Globe,
  Loader2,
  MessageSquareMore,
  Search,
  Send,
  AlertTriangle,
  Users,
  Wrench,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentToolEvent } from '@/types/agent'
import { ToolResultCard } from './ToolResultCard'

interface ToolCollapsedProps {
  toolEvent: AgentToolEvent
}

type PhaseMeta = {
  label: string
  badgeClassName: string
  icon: ComponentType<{ className?: string }>
}

const PHASE_META: Record<AgentToolEvent['phase'], PhaseMeta> = {
  waiting_input: {
    label: 'Aguardando confirmação',
    badgeClassName: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
    icon: AlertTriangle,
  },
  started: {
    label: 'Executando',
    badgeClassName: 'border-sky-500/30 bg-sky-500/10 text-sky-200',
    icon: Loader2,
  },
  completed: {
    label: 'Concluído',
    badgeClassName: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
    icon: CheckCircle2,
  },
  failed: {
    label: 'Falhou',
    badgeClassName: 'border-red-500/30 bg-red-500/10 text-red-200',
    icon: AlertTriangle,
  },
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

function truncateText(value: string, limit: number): string {
  if (value.length <= limit) {
    return value
  }

  return `${value.slice(0, limit - 1).trimEnd()}…`
}

function buildToolPreview(toolEvent: AgentToolEvent): string {
  const preview =
    toolEvent.error ||
    toolEvent.outputPreview ||
    toolEvent.inputPreview ||
    'Detalhes da execução disponíveis para expandir.'

  return truncateText(preview, 180)
}

function resolveToolIcon(toolName: string) {
  const normalized = toolName.toLowerCase()

  if (normalized.includes('send')) {
    return Send
  }
  if (normalized.includes('contact')) {
    return Users
  }
  if (normalized.includes('message') || normalized.includes('read')) {
    return MessageSquareMore
  }
  if (normalized.includes('search')) {
    return Search
  }
  if (normalized.includes('fetch') || normalized.includes('web')) {
    return Globe
  }
  if (normalized.includes('database') || normalized.includes('menu')) {
    return Database
  }

  return Wrench
}

export function ToolCollapsed({ toolEvent }: ToolCollapsedProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const label = toolEvent.displayName || toolEvent.toolName
  const phaseMeta = PHASE_META[toolEvent.phase]
  const PhaseIcon = phaseMeta.icon
  const ToolIcon = resolveToolIcon(toolEvent.toolName)
  const preview = buildToolPreview(toolEvent)
  const startedAt = formatTimestamp(toolEvent.startedAt || toolEvent.persistedAt)
  const finishedAt = formatTimestamp(toolEvent.finishedAt)

  return (
    <div className="flex items-start gap-3 py-1">
      <div className="mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl border border-primary/30 bg-[radial-gradient(circle_at_top,_rgba(236,72,153,0.22),_transparent_55%),linear-gradient(135deg,_rgba(139,92,246,0.22),_rgba(17,12,37,0.92))] text-[#F5EBFF] shadow-[0_12px_24px_rgba(11,6,28,0.35)]">
        <ToolIcon className="h-4 w-4" />
      </div>

      <div className="w-full max-w-[78%] overflow-hidden rounded-[20px] border border-[#3A2C70] bg-[linear-gradient(180deg,_rgba(31,23,58,0.98)_0%,_rgba(18,13,36,0.98)_100%)] shadow-[0_14px_34px_rgba(11,6,28,0.28)]">
        <div className="flex items-start gap-3 px-4 py-3.5">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-text-light">{label}</p>
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium',
                  phaseMeta.badgeClassName
                )}
              >
                <PhaseIcon
                  className={cn('h-3.5 w-3.5', toolEvent.phase === 'started' && 'animate-spin')}
                />
                <span>{phaseMeta.label}</span>
              </span>
            </div>

            <p className="mt-1 text-xs tracking-[0.16em] text-[#9489C2]">{toolEvent.toolName}</p>
            <p className="mt-3 text-sm leading-6 text-[#EEE7FF]">{preview}</p>

            <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[#B4AAD9]">
              {startedAt && (
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
                  Início {startedAt}
                </span>
              )}
              {finishedAt && (
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
                  Fim {finishedAt}
                </span>
              )}
              {toolEvent.traceId && (
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
                  Trace {toolEvent.traceId.slice(0, 12)}
                </span>
              )}
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsExpanded((current) => !current)}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? 'Ocultar detalhes da ferramenta' : 'Expandir detalhes da ferramenta'}
            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl border border-[#4A3A85] bg-[#221A44] text-[#E9D5FF] transition-all hover:border-primary/60 hover:bg-[#2A2050]"
          >
            <ChevronDown
              className={cn('h-4 w-4 transition-transform duration-200', isExpanded && 'rotate-180')}
            />
          </button>
        </div>

        {isExpanded && (
          <div className="border-t border-white/10 bg-black/10 px-4 py-4">
            <ToolResultCard toolEvent={toolEvent} />
          </div>
        )}
      </div>
    </div>
  )
}
