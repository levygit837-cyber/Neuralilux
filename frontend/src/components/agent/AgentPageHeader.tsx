'use client'

import { Settings, Loader2 } from 'lucide-react'
import { useModels } from '@/hooks/useModels'

interface AgentPageHeaderProps {
  agentName?: string
  agentId?: string
  workspace?: string
  temperature?: number
  isActive?: boolean
}

export function AgentPageHeader({
  agentName = 'Agente IA',
  agentId = 'agt_default',
  workspace = 'Principal',
  temperature = 0.3,
  isActive = true,
}: AgentPageHeaderProps) {
  const { currentModel, isLoading } = useModels()
  
  // Usar modelo dinâmico do LM Studio ou fallback
  const displayModelName = isLoading 
    ? 'Carregando...' 
    : (currentModel?.name || 'Local Model')
  const temperaturePercent = Math.round(temperature * 100)

  return (
    <header className="h-16 bg-[#1A1333]/90 backdrop-blur-xl border-b border-border-color flex items-center justify-between px-6 z-10 shrink-0 shadow-sm">
      {/* Left: Identity & Status */}
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-hover border border-border-color">
          <svg className="w-5 h-5 text-primary-light" fill="currentColor" viewBox="0 0 256 256">
            <path d="M200,48H136V16a8,8,0,0,0-16,0V48H56A32,32,0,0,0,24,80V192a32,32,0,0,0,32,32H200a32,32,0,0,0,32-32V80A32,32,0,0,0,200,48ZM172,96a12,12,0,1,1-12,12A12,12,0,0,1,172,96ZM96,96a12,12,0,1,1-12,12A12,12,0,0,1,96,96Zm88,80H72a8,8,0,0,1,0-16H184a8,8,0,0,1,0,16Z" />
          </svg>
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-lg text-text-light leading-none">{agentName}</h1>
            <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-success/10 border border-success/20 text-success text-xs font-medium">
              <span
                className={`w-1.5 h-1.5 rounded-full bg-success ${isActive ? 'animate-pulse' : ''}`}
              />
              {isActive ? 'Ativo' : 'Inativo'}
            </span>
          </div>
          <span className="text-xs text-text-muted mt-1">
            ID: {agentId} • Workspace: {workspace}
          </span>
        </div>
      </div>

      {/* Right: Technical Controls */}
      <div className="flex items-center gap-5">
        {/* Model Badge */}
        <div className="flex items-center gap-2 bg-dark border border-border-color rounded-lg px-3 py-1.5">
          <svg className="w-4 h-4 text-primary" fill="currentColor" viewBox="0 0 256 256">
            <path d="M247.9,89.7A8,8,0,0,0,240,88H216V80a88,88,0,0,0-160.6-49.8A8,8,0,1,0,67.4,41.8,72,72,0,0,1,200,80v8H160a8,8,0,0,0-7.9,6.7l-16,112A8,8,0,0,0,144,216h64a8,8,0,0,0,7.9-6.7l16-112A8,8,0,0,0,247.9,89.7Z" />
          </svg>
          <span className="text-xs font-mono text-text-gray flex items-center gap-1">
            {isLoading && <Loader2 className="h-3 w-3 animate-spin" />}
            {displayModelName}
          </span>
        </div>

        {/* Temperature Indicator */}
        <div className="group flex items-center gap-2 cursor-help relative">
          <svg className="w-4 h-4 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <div className="w-20 h-1.5 bg-border-color rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-accent rounded-full"
              style={{ width: `${temperaturePercent}%` }}
            />
          </div>
          <span className="text-xs font-mono text-text-muted">{temperature.toFixed(1)}</span>
          <div className="absolute -bottom-8 right-0 bg-card border border-border-color text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-lg text-text-gray">
            Temperatura de Criação
          </div>
        </div>

        {/* Settings Button */}
        <button className="w-8 h-8 rounded-md flex items-center justify-center text-text-muted hover:text-text-light hover:bg-hover transition-colors border border-transparent hover:border-border-color">
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
