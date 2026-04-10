'use client'

import { Sidebar } from '@/components/layout/Sidebar'
import { WhatsAppChat } from '@/components/chat/WhatsAppChat'

export default function ChatPage() {
  return (
    <div className="flex h-screen overflow-hidden bg-brand-base">
      <Sidebar />
      <WhatsAppChat />
    </div>
  )
}
