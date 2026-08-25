import { create } from 'zustand'

interface AssistantState {
  open: boolean
  /** 当前线程 id；undefined 表示新会话 */
  threadId: string | undefined
  openPanel: () => void
  closePanel: () => void
  togglePanel: () => void
  switchThread: (threadId: string | undefined) => void
}

export const useAssistantStore = create<AssistantState>((set) => ({
  open: false,
  threadId: undefined,
  openPanel: () => set({ open: true }),
  closePanel: () => set({ open: false }),
  togglePanel: () => set((state) => ({ open: !state.open })),
  switchThread: (threadId) => set({ threadId }),
}))
