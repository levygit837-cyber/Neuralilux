'use client'

import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { WhatsAppChat } from '@/components/chat/WhatsAppChat'

export default function ChatPage() {
  return (
    <div className="flex h-screen overflow-hidden bg-dark">
      <Sidebar />
      <div className="flex min-h-0 flex-1 flex-col">
        <Header title="Chat" />
        <div className="min-h-0 flex-1 overflow-hidden">
          <WhatsAppChat />
        </div>
      </div>
    </div>
  )
}
