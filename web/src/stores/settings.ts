import { create } from 'zustand'

export type ColorScheme = 'cn' | 'us'

interface SettingsState {
  colorScheme: ColorScheme
  setColorScheme: (scheme: ColorScheme) => void
}

const STORAGE_KEY = 'color_scheme'

const getStoredScheme = (): ColorScheme => {
  return localStorage.getItem(STORAGE_KEY) === 'us' ? 'us' : 'cn'
}

export const useSettingsStore = create<SettingsState>((set) => ({
  colorScheme: getStoredScheme(),

  setColorScheme: (scheme) => {
    localStorage.setItem(STORAGE_KEY, scheme)
    set({ colorScheme: scheme })
  },
}))

export function useColorScheme(): ColorScheme {
  return useSettingsStore((state) => state.colorScheme)
}
