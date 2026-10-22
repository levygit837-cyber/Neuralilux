export interface ThemeConfig {
  theme: 'dark' | 'light'
  language: string
}

export interface Settings {
  theme: ThemeConfig
}

export type SettingsTab = 'general' | 'instance' | 'gateways'