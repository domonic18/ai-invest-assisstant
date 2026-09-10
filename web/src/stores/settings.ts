import { create } from 'zustand'
import { StorageKey, type MovingAverageConfig, type UserSettings } from '@ai-invest/shared'

import { fetchUserSettings, updateUserSettings } from '@/api/settings'

export type ColorScheme = 'cn' | 'us'

const DEFAULT_MA_CONFIGS: MovingAverageConfig[] = [
  { period: 5, color: '#f0b429', enabled: true },
  { period: 10, color: '#9d7ff5', enabled: true },
  { period: 20, color: '#3fb6e0', enabled: true },
  { period: 30, color: '#e8833a', enabled: true },
  { period: 60, color: '#c0c4d0', enabled: true },
  { period: 120, color: '#22c55e', enabled: false },
]

const DEFAULT_USER_SETTINGS: UserSettings = {
  maConfigs: DEFAULT_MA_CONFIGS,
}

const getStoredScheme = (): ColorScheme => {
  return localStorage.getItem(StorageKey.settings.colorScheme) === 'us' ? 'us' : 'cn'
}

const getStoredCalendarDetailCollapsed = (): boolean => {
  return localStorage.getItem(StorageKey.settings.calendarDetailCollapsed) === '1'
}

const getStoredToken = (): string | null => {
  return localStorage.getItem(StorageKey.auth.accessToken)
}

interface SettingsState {
  colorScheme: ColorScheme
  calendarDetailCollapsed: boolean
  userSettings: UserSettings
  isLoadingSettings: boolean
  settingsError: string | null

  setColorScheme: (scheme: ColorScheme) => void
  toggleCalendarDetailCollapsed: () => void
  initialize: () => Promise<void>
  updateMaConfigs: (configs: MovingAverageConfig[]) => Promise<void>
  updateTrackedIndexes: (codes: string[] | null) => Promise<void>
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  colorScheme: getStoredScheme(),
  calendarDetailCollapsed: getStoredCalendarDetailCollapsed(),
  userSettings: DEFAULT_USER_SETTINGS,
  isLoadingSettings: false,
  settingsError: null,

  setColorScheme: (scheme) => {
    localStorage.setItem(StorageKey.settings.colorScheme, scheme)
    set({ colorScheme: scheme })
  },

  toggleCalendarDetailCollapsed: () =>
    set((state) => {
      const next = !state.calendarDetailCollapsed
      localStorage.setItem(StorageKey.settings.calendarDetailCollapsed, next ? '1' : '0')
      return { calendarDetailCollapsed: next }
    }),

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
    const next: UserSettings = { ...get().userSettings, maConfigs: configs }
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

  updateTrackedIndexes: async (codes) => {
    const next: UserSettings = { ...get().userSettings, trackedIndexCodes: codes }
    set({ userSettings: next })
    if (!getStoredToken()) return
    try {
      const saved = await updateUserSettings(next)
      set({ userSettings: saved, settingsError: null })
    } catch (error) {
      set({
        settingsError: error instanceof Error ? error.message : '保存跟踪指数失败',
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
