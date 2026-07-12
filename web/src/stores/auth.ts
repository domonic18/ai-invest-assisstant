import { create } from 'zustand'

interface AuthState {
  token: string | null
  user: { id: string; username: string } | null
  setToken: (token: string | null) => void
  setUser: (user: { id: string; username: string } | null) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('access_token'),
  user: null,
  setToken: (token) => {
    if (token) localStorage.setItem('access_token', token)
    else localStorage.removeItem('access_token')
    set({ token })
  },
  setUser: (user) => set({ user }),
}))
