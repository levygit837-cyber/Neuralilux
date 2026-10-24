'use client'

import { SettingsHeader } from '@/components/settings/SettingsHeader'
import { CompanyProfileCard } from '@/components/settings/CompanyProfileCard'
import { AIAgentCard } from '@/components/settings/AIAgentCard'
import { InferenceProviderCard } from '@/components/settings/InferenceProviderCard'
import { WhatsAppConnectionCard } from '@/components/settings/WhatsAppConnectionCard'
import { ThemeAppearanceCard } from '@/components/settings/ThemeAppearanceCard'
import { GatewaysPanel } from '@/components/settings/GatewaysPanel'
import { useCompanySettings } from '@/hooks/useCompanySettings'
import { useSettingsStore } from '@/stores/useSettingsStore'

export default function SettingsPage() {
  const { activeTab } = useSettingsStore()
  const companySettings = useCompanySettings()

  return (
    <div className="flex-1 p-4 sm:p-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <SettingsHeader />

        {activeTab === 'general' && (
          <div className="space-y-6">
            <CompanyProfileCard settings={companySettings} />
            <InferenceProviderCard />
            <AIAgentCard settings={companySettings} />
            <ThemeAppearanceCard />
          </div>
        )}

        {activeTab === 'instance' && (
          <div className="space-y-6">
            <WhatsAppConnectionCard />
          </div>
        )}

        {activeTab === 'gateways' && <GatewaysPanel />}
      </div>
    </div>
  )
}
