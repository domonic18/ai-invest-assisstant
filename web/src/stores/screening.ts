import { create } from 'zustand'

import type { StockScreeningResult } from '@/stores/assistant'

/**
 * 问财筛选临时结果（SPA 会话级，刷新即清，零落库）。
 *
 * 独立 slice 的原因：usePageAssistantResult 消费即清空 assistant store，
 * /screening 页需要独立接住最近一次筛选结果。
 */
interface ScreeningState {
  result: StockScreeningResult | null
  setResult: (result: StockScreeningResult | null) => void
}

export const useScreeningStore = create<ScreeningState>((set) => ({
  result: null,
  setResult: (result) => set({ result }),
}))
