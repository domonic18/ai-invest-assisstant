import { create } from 'zustand'

/** deepagents TodoList 步骤 */
export interface TodoStep {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

/** 由 Assistant Agent 产生、需要回写到页面的结构化结果。 */
export interface PageAssistantResult {
  type: 'industry_chain.analysis_complete'
  industry: string
  versionId: number
  versionNo: number
  createdAt?: string
}

interface AssistantState {
  open: boolean
  /** 当前线程 id；undefined 表示新会话 */
  threadId: string | undefined
  /** 当前线程的执行计划（updates 事件驱动）；切换线程时清空 */
  todos: TodoStep[] | undefined
  /** 打开面板后自动发送的问题 */
  pendingQuestion: string | undefined
  /** Agent 完成页面级任务后回写的结构化结果 */
  pageResult: PageAssistantResult | null
  openPanel: () => void
  closePanel: () => void
  togglePanel: () => void
  switchThread: (threadId: string | undefined) => void
  setTodos: (todos: TodoStep[] | undefined) => void
  /** 打开 AI 助手面板并预置一条待发送问题 */
  sendQuestion: (question: string) => void
  clearPendingQuestion: () => void
  setPageResult: (result: PageAssistantResult | null) => void
}

export const useAssistantStore = create<AssistantState>((set) => ({
  open: false,
  threadId: undefined,
  todos: undefined,
  pendingQuestion: undefined,
  pageResult: null,
  openPanel: () => set({ open: true }),
  closePanel: () => set({ open: false }),
  togglePanel: () => set((state) => ({ open: !state.open })),
  switchThread: (threadId) => set({ threadId, todos: undefined }),
  setTodos: (todos) => set({ todos }),
  sendQuestion: (question) => set({ open: true, pendingQuestion: question }),
  clearPendingQuestion: () => set({ pendingQuestion: undefined }),
  setPageResult: (pageResult) => set({ pageResult }),
}))
