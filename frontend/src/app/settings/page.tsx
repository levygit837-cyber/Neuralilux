'use client'

import { Sidebar } from '@/components/layout/Sidebar'
import { SettingsHeader } from '@/components/settings/SettingsHeader'
import { CompanyProfileCard } from '@/components/settings/CompanyProfileCard'
import { AIAgentCard } from '@/components/settings/AIAgentCard'
import { InferenceProviderCard } from '@/components/settings/InferenceProviderCard'
import { WhatsAppConnectionCard } from '@/components/settings/WhatsAppConnectionCard'
import { ThemeAppearanceCard } from '@/components/settings/ThemeAppearanceCard'
import { useSettingsStore } from '@/stores/useSettingsStore'

export default function SettingsPage() {
  const { activeTab } = useSettingsStore()

  return (
    <div className="flex min-h-screen bg-dark">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <div className="flex-1 overflow-auto p-8">
          <div className="mx-auto max-w-4xl space-y-6">
            {/* Header with Tabs */}
            <SettingsHeader />

            {/* General Tab Content */}
            {activeTab === 'general' && (
              <div className="space-y-6">
                <CompanyProfileCard />
                <InferenceProviderCard />
                <AIAgentCard />
                <ThemeAppearanceCard />
              </div>
            )}

            {/* Instance Tab Content */}
            {activeTab === 'instance' && (
              <div className="space-y-6">
                <WhatsAppConnectionCard />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
