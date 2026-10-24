'use client'

import { useSettingsStore } from '@/stores/useSettingsStore'
import type { SettingsTab } from '@/types/settings'

const TABS: { id: SettingsTab; label: string }[] = [
  { id: 'general', label: 'Geral' },
  { id: 'instance', label: 'Instância' },
  { id: 'gateways', label: 'Gateways' },
]

export function SettingsHeader() {
  const { activeTab, setActiveTab } = useSettingsStore()

  return (
    <div className="space-y-5">
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-content-light">Configurações</h1>
      </div>

      {/* Tabs */}
      <div className="border-b border-brand-border">
        <div className="flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              aria-pressed={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-primary-light'
                  : 'text-content-gray hover:text-content-light'
              }`}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-primary" />
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}