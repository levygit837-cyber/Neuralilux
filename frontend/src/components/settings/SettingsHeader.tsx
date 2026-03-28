'use client'

import { Search } from 'lucide-react'
import { useSettingsStore } from '@/stores/useSettingsStore'
import type { SettingsTab } from '@/types/settings'

const TABS: { id: SettingsTab; label: string }[] = [
  { id: 'general', label: 'Geral' },
  { id: 'instance', label: 'Instância' },
]

export function SettingsHeader() {
  const { activeTab, setActiveTab } = useSettingsStore()

  return (
    <div className="space-y-5">
      {/* Header Row */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-light">Configurações</h1>
        <div className="flex h-10 w-80 items-center gap-2 rounded-xl border border-border-color bg-card px-3.5">
          <Search className="h-4 w-4 text-text-gray" />
          <input
            type="text"
            placeholder="Buscar configurações..."
            className="flex-1 bg-transparent text-sm text-text-light placeholder:text-text-gray outline-none"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-border-color">
        <div className="flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-primary'
                  : 'text-text-gray hover:text-text-light'
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