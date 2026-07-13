import { create } from 'zustand'

import type { User } from '@ai-invest/shared'

import { fetchCurrentUser } from '@/api/auth'

interface AuthState {
  token: string | null
  user: User | null
  isInitialized: boolean
  isLoading: boolean
  error: string | null
  isAdmin: boolean
  setToken: (token: string | null) => void
  setUser: (user: User | null) => void
  initialize: () => Promise<void>
  login: (token: string, user: User) => void
  logout: () => void
  clearError: () => void
}

const getStoredToken = (): string | null => {
  return localStorage.getItem('access_token')
}

export const useAuthStore = create<AuthState>((set) => ({
  token: getStoredToken(),
  user: null,
  isInitialized: false,
  isLoading: false,
  error: null,
  isAdmin: false,

  setToken: (token) => {
    if (token) {
      localStorage.setItem('access_token', token)
    } else {
      localStorage.removeItem('access_token')
    }
    set({ token })
  },

  setUser: (user) => {
    set({ user, isAdmin: user?.isAdmin ?? false })
  },

  initialize: async () => {
    const token = getStoredToken()
    if (!token) {
      set({ isInitialized: true, token: null })
      return
    }

    set({ isLoading: true, error: null })
    try {
      const user = await fetchCurrentUser()
      set({
        token,
        user,
        isAdmin: user.isAdmin,
        isInitialized: true,
        isLoading: false,
      })
    } catch (error) {
      localStorage.removeItem('access_token')
      set({
        token: null,
        user: null,
        isAdmin: false,
        isInitialized: true,
        isLoading: false,
        error: error instanceof Error ? error.message : '会话初始化失败',
      })
    }
  },

  login: (token, user) => {
    localStorage.setItem('access_token', token)
    set({
      token,
      user,
      isAdmin: user.isAdmin,
      error: null,
    })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    set({
      token: null,
      user: null,
      isAdmin: false,
      error: null,
    })
  },

  clearError: () => set({ error: null }),
}))
