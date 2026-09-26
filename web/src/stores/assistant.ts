import { create } from 'zustand'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'

const USE_KB_STORAGE_KEY = 'ai-invest.assistant.useKb.v1'

function readUseKb(): boolean {
  try {
    return localStorage.getItem(USE_KB_STORAGE_KEY) !== 'false'
  } catch {
    return true
  }
}

function persistUseKb(value: boolean): void {
  try {
    localStorage.setItem(USE_KB_STORAGE_KEY, String(value))
  } catch {
    // ignore storage errors
  }
}

/** deepagents TodoList 步骤 */
export interface TodoStep {
  content: string
  status: 'pending' | 'in_progress' | 'completed'
}

/** 由 Assistant Agent 产生、需要回写到页面的结构化结果。 */
export type PageAssistantResult =
  | ChainAnalysisResult
  | StockDailyAnalysisResult
  | MarketDailyReviewResult
  | LimitUpAttributionResult
  | SectorAnomalyResult
  | StockAnomalyResult
  | StockScreeningResult
  | KlineDrawingResult
  | PaperTradingResult

/** 产业链分析完成回写 */
export interface ChainAnalysisResult {
  type: typeof PAGE_EVENT_TYPES.chainAnalysis
  industry: string
  versionId: number
  versionNo: number
  createdAt?: string
}

/** 个股每日 AI 分析完成回写 */
export interface StockDailyAnalysisResult {
  type: typeof PAGE_EVENT_TYPES.stockDailyAnalysis
  stockCode: string
  tradeDate: string
}

/** 大盘每日复盘完成回写 */
export interface MarketDailyReviewResult {
  type: typeof PAGE_EVENT_TYPES.marketDailyReview
  tradeDate: string
}

/** 涨停 AI 归因完成回写 */
export interface LimitUpAttributionResult {
  type: typeof PAGE_EVENT_TYPES.limitUpAttribution
  tradeDate: string
}

/** 板块异动 AI 归因完成回写 */
export interface SectorAnomalyResult {
  type: typeof PAGE_EVENT_TYPES.sectorAnomaly
  tradeDate: string
}

/** 个股异动 AI 归因完成回写 */
export interface StockAnomalyResult {
  type: typeof PAGE_EVENT_TYPES.stockAnomaly
  tradeDate: string
}

/** 问财选股结果行：固定两列 + 问财原始中文列（列名即键，动态渲染） */
export interface StockScreeningRow {
  stockCode: string
  stockName: string
  [column: string]: unknown
}

/** 问财 AI 选股完成回写（全量行数据搭车，结果为临时内容、不落库） */
export interface StockScreeningResult {
  type: typeof PAGE_EVENT_TYPES.stockScreening
  query: string
  total: number
  truncated: boolean
  columns: string[]
  stocks: StockScreeningRow[]
}

/** AI K 线画线完成回写（AI 图层刷新 + 会话内直达标的图表页） */
export interface KlineDrawingResult {
  type: typeof PAGE_EVENT_TYPES.klineDrawing
  targetType: 'stock' | 'index' | 'sector'
  targetCode: string
  period: string
  count: number
  sectorType?: string
}

/** 交易 Agent 委托回写（下单成功事件，订阅页刷新模拟盘数据） */
export interface PaperTradingResult {
  type: typeof PAGE_EVENT_TYPES.paperTrading
  action: string
  clOrdId?: string
  symbol?: string
  side?: string
  volume?: number
}

/** ask_user 问题卡选项 */
export interface QuestionOption {
  value: string
  label: string
}

/** Agent ask_user 下发的结构化问题（选项点击作为新消息续跑对话） */
export interface QuestionCard {
  question: string
  options: QuestionOption[]
  default?: string | null
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
  /** ask_user 问题卡（仅最新一张；新问题或用户回复即清空） */
  questionCard: QuestionCard | null
  /** 对话「使用知识库」开关（localStorage 持久化，随 run metadata 传后端） */
  useKb: boolean
  openPanel: () => void
  closePanel: () => void
  togglePanel: () => void
  switchThread: (threadId: string | undefined) => void
  setTodos: (todos: TodoStep[] | undefined) => void
  /** 打开 AI 助手面板并预置一条待发送问题（同时清空待答问题卡） */
  sendQuestion: (question: string) => void
  clearPendingQuestion: () => void
  setPageResult: (result: PageAssistantResult | null) => void
  setQuestionCard: (card: QuestionCard | null) => void
  setUseKb: (value: boolean) => void
}

export const useAssistantStore = create<AssistantState>((set) => ({
  open: false,
  threadId: undefined,
  todos: undefined,
  pendingQuestion: undefined,
  pageResult: null,
  questionCard: null,
  useKb: readUseKb(),
  openPanel: () => set({ open: true }),
  closePanel: () => set({ open: false }),
  togglePanel: () => set((state) => ({ open: !state.open })),
  switchThread: (threadId) => set({ threadId, todos: undefined, questionCard: null }),
  setTodos: (todos) => set({ todos }),
  sendQuestion: (question) => set({ open: true, pendingQuestion: question, questionCard: null }),
  clearPendingQuestion: () => set({ pendingQuestion: undefined }),
  setPageResult: (pageResult) => set({ pageResult }),
  setQuestionCard: (questionCard) => set({ questionCard }),
  setUseKb: (value) => {
    set({ useKb: value })
    persistUseKb(value)
  },
}))
