'use client'

import { Sidebar } from '@/components/layout/Sidebar'
import { AgentChat } from '@/components/agent/AgentChat'

export default function AgentPage() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      {/* bg-dots applied here so the dot pattern shows behind the entire content area */}
      <main className="flex min-h-0 flex-1 flex-col relative bg-dots bg-dark">
        <AgentChat />
      </main>
    </div>
  )
}
