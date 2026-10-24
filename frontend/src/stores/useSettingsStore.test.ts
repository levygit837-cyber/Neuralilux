import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const KEY = 'neuralilux-settings-storage'

/** localStorage em memória; o ambiente de teste é `node`. */
function fakeLocalStorage(initial: Record<string, string>) {
  const data = new Map(Object.entries(initial))
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => void data.set(key, value),
    removeItem: (key: string) => void data.delete(key),
    data,
  }
}

/** Importa o store do zero para ele reidratar do localStorage falso. */
async function loadStoreWith(persisted: unknown) {
  const storage = fakeLocalStorage(persisted === undefined ? {} : { [KEY]: JSON.stringify(persisted) })
  vi.stubGlobal('localStorage', storage)
  vi.resetModules()
  const { useSettingsStore } = await import('@/stores/useSettingsStore')
  return { store: useSettingsStore, storage }
}

describe('useSettingsStore: migração v3 → v4', () => {
  beforeEach(() => vi.resetModules())
  afterEach(() => vi.unstubAllGlobals())

  it('estado v3 persistido vira só activeTab', async () => {
    const { store } = await loadStoreWith({
      version: 3,
      state: {
        settings: { theme: { theme: 'light', language: 'English' }, whatsapp: { apiKey: 'segredo' } },
        activeTab: 'gateways',
      },
    })

    expect(store.getState().activeTab).toBe('gateways')
    expect(store.getState()).not.toHaveProperty('settings')
  })

  it('v3 sem aba guardada cai em general', async () => {
    const { store } = await loadStoreWith({
      version: 3,
      state: { settings: { theme: { theme: 'dark', language: 'Português (BR)' } } },
    })

    expect(store.getState().activeTab).toBe('general')
  })

  it('ao trocar de aba grava só activeTab, sem tema nem idioma', async () => {
    const { store, storage } = await loadStoreWith({
      version: 3,
      state: { settings: { theme: { theme: 'light', language: 'English' } }, activeTab: 'general' },
    })

    store.getState().setActiveTab('instance')

    const saved = JSON.parse(storage.data.get(KEY) as string)
    expect(saved).toEqual({ version: 4, state: { activeTab: 'instance' } })
  })
})
