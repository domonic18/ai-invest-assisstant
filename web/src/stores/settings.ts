import { create } from 'zustand'
import type { MovingAverageConfig, UserSettings } from '@ai-invest/shared'

import { fetchUserSettings, updateUserSettings } from '@/api/settings'

export type ColorScheme = 'cn' | 'us'

const STORAGE_KEY = 'color_scheme'

const DEFAULT_MA_CONFIGS: MovingAverageConfig[] = [
  { period: 5, color: '#f0b429', enabled: true },
  { period: 10, color: '#9d7ff5', enabled: true },
  { period: 20, color: '#3fb6e0', enabled: true },
  { period: 30, color: '#e8833a', enabled: true },
  { period: 60, color: '#c0c4d0', enabled: false },
  { period: 120, color: '#22c55e', enabled: false },
]

const DEFAULT_USER_SETTINGS: UserSettings = {
  maConfigs: DEFAULT_MA_CONFIGS,
}

const getStoredScheme = (): ColorScheme => {
  return localStorage.getItem(STORAGE_KEY) === 'us' ? 'us' : 'cn'
}

const getStoredToken = (): string | null => {
  return localStorage.getItem('access_token')
}

interface SettingsState {
  colorScheme: ColorScheme
  userSettings: UserSettings
  isLoadingSettings: boolean
  settingsError: string | null

  setColorScheme: (scheme: ColorScheme) => void
  initialize: () => Promise<void>
  updateMaConfigs: (configs: MovingAverageConfig[]) => Promise<void>
}

export const useSettingsStore = create<SettingsState>((set) => ({
  colorScheme: getStoredScheme(),
  userSettings: DEFAULT_USER_SETTINGS,
  isLoadingSettings: false,
  settingsError: null,

  setColorScheme: (scheme) => {
    localStorage.setItem(STORAGE_KEY, scheme)
    set({ colorScheme: scheme })
  },

  initialize: async () => {
    if (!getStoredToken()) {
      set({ userSettings: DEFAULT_USER_SETTINGS, isLoadingSettings: false })
      return
    }
    set({ isLoadingSettings: true, settingsError: null })
    try {
      const settings = await fetchUserSettings()
      set({ userSettings: settings, isLoadingSettings: false })
    } catch (error) {
      set({
        userSettings: DEFAULT_USER_SETTINGS,
        isLoadingSettings: false,
        settingsError: error instanceof Error ? error.message : '加载个人配置失败',
      })
    }
  },

  updateMaConfigs: async (configs) => {
    const next: UserSettings = { maConfigs: configs }
    set({ userSettings: next })
    if (!getStoredToken()) return
    try {
      const saved = await updateUserSettings(next)
      set({ userSettings: saved, settingsError: null })
    } catch (error) {
      set({
        settingsError: error instanceof Error ? error.message : '保存均线配置失败',
      })
      throw error
    }
  },
}))

export function useColorScheme(): ColorScheme {
  return useSettingsStore((state) => state.colorScheme)
}

export function useMaConfigs(): MovingAverageConfig[] {
  return useSettingsStore((state) => state.userSettings.maConfigs)
}
