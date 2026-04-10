'use client'

import { useState } from 'react'
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
import type { AgentToolEvent } from '@/types/agent'
import { ToolResultCard } from './ToolResultCard'

interface AgentToolCardProps {
  toolEvent: AgentToolEvent
}

const PHASE_CONFIG = {
  waiting_input: {
    label: 'Aguardando',
    badgeClass: 'bg-warning/10 text-warning border-warning/20',
    iconClass: 'text-warning bg-warning/10',
    borderClass: 'border-l-warning',
    shadowClass: '',
    BadgeIcon: AlertTriangle,
  },
  started: {
    label: 'Executando',
    badgeClass: 'bg-warning/10 text-warning border-warning/20',
    iconClass: 'text-warning bg-warning/10',
    borderClass: 'border-l-warning',
    shadowClass: 'shadow-[0_0_15px_rgba(245,158,11,0.05)]',
    BadgeIcon: Loader2,
  },
  completed: {
    label: 'Sucesso',
    badgeClass: 'bg-success/10 text-success border-success/20',
    iconClass: 'text-success bg-success/10',
    borderClass: 'border-l-success',
    shadowClass: '',
    BadgeIcon: CheckCircle2,
  },
  failed: {
    label: 'Falhou',
    badgeClass: 'bg-error/10 text-error border-error/20',
    iconClass: 'text-error bg-error/10',
    borderClass: 'border-l-error',
    shadowClass: '',
    BadgeIcon: AlertTriangle,
  },
} as const

function resolveToolIcon(toolName: string) {
  const normalized = toolName.toLowerCase()
  if (normalized.includes('send')) return Send
  if (normalized.includes('contact')) return Users
  if (normalized.includes('message') || normalized.includes('read')) return MessageSquareMore
  if (normalized.includes('search')) return Search
  if (normalized.includes('fetch') || normalized.includes('web')) return Globe
  if (normalized.includes('database') || normalized.includes('menu')) return Database
  return Wrench
}

export function AgentToolCard({ toolEvent }: AgentToolCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const config = PHASE_CONFIG[toolEvent.phase]
  const { BadgeIcon } = config
  const ToolIcon = resolveToolIcon(toolEvent.toolName)
  const displayName = toolEvent.displayName ?? toolEvent.toolName
  const isExecuting = toolEvent.phase === 'started' || toolEvent.phase === 'waiting_input'

  return (
    <div
      className={`w-full max-w-3xl bg-card border border-border-color border-l-[3px] ${config.borderClass} rounded-xl shadow-lg z-10 overflow-hidden transition-transform duration-200 hover:-translate-y-0.5 ${config.shadowClass}`}
    >
      {/* Header row */}
      <button
        type="button"
        onClick={() => setIsExpanded((prev) => !prev)}
        className="w-full flex items-center justify-between p-3 text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded flex items-center justify-center ${config.iconClass}`}>
            <ToolIcon className="w-4 h-4" />
          </div>
          <span className="text-[14px] font-mono text-text-gray">{displayName}</span>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`px-2 py-0.5 text-[11px] font-medium rounded uppercase tracking-wide border flex items-center gap-1.5 ${config.badgeClass}`}
          >
            <BadgeIcon
              className={`w-3 h-3 ${isExecuting ? 'animate-spin-slow' : ''}`}
            />
            {config.label}
          </span>
          <ChevronDown
            className={`w-4 h-4 text-text-muted transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {/* Expanded payload */}
      {isExpanded && (
        <div className="border-t border-border-color bg-[#0A0714] rounded-b-xl px-4 py-4">
          <ToolResultCard toolEvent={toolEvent} />
        </div>
      )}
    </div>
  )
}
