import { message } from 'antd'

import { PAGE_EVENT_TYPES } from '@ai-invest/shared'

import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { useScreeningStore } from '@/stores/screening'

/**
 * /screening 页对助手事件的桥接：其他页面经侧边栏对话触发问财筛选后，
 * 点「查看筛选结果」导航到本页时，在此消费事件回填临时 store。
 * 页内搜索走直查 API，不经过本桥。
 */
export function useStockScreeningEvent() {
  usePageAssistantResult(PAGE_EVENT_TYPES.stockScreening, (result) => {
    useScreeningStore.getState().setResult(result)
    message.success(`筛选完成：命中 ${result.total} 只`)
    return true
  })
}
