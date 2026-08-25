import { create } from 'zustand'

/** deepagents TodoList 步骤 */
export interface TodoStep {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

interface AssistantState {
  open: boolean
  /** 当前线程 id；undefined 表示新会话 */
  threadId: string | undefined
  /** 当前线程的执行计划（updates 事件驱动）；切换线程时清空 */
  todos: TodoStep[] | undefined
  openPanel: () => void
  closePanel: () => void
  togglePanel: () => void
  switchThread: (threadId: string | undefined) => void
  setTodos: (todos: TodoStep[] | undefined) => void
}

export const useAssistantStore = create<AssistantState>((set) => ({
  open: false,
  threadId: undefined,
  todos: undefined,
  openPanel: () => set({ open: true }),
  closePanel: () => set({ open: false }),
  togglePanel: () => set((state) => ({ open: !state.open })),
  switchThread: (threadId) => set({ threadId, todos: undefined }),
  setTodos: (todos) => set({ todos }),
}))
