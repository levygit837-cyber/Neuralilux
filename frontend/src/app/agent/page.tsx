'use client'

import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { AgentChat } from '@/components/agent/AgentChat'

export default function AgentPage() {
  return (
    <div className="flex h-screen overflow-hidden bg-dark">
      <Sidebar />
      <div className="flex min-h-0 flex-1 flex-col">
        <Header title="Agent" />
        <div className="min-h-0 flex-1 overflow-hidden">
          <AgentChat />
        </div>
      </div>
    </div>
  )
}
