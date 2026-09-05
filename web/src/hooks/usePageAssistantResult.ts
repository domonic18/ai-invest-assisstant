import { useEffect } from 'react'

import { useAssistantStore, type PageAssistantResult } from '@/stores/assistant'

/**
 * 订阅助手页面回写事件（pageEvents 注册表中的类型）。
 *
 * onResult 返回 true 表示事件已消费（store 中的事件清空）；
 * 返回 false 保留事件，供其他页面（或本页后续状态）继续消费。
 */
export function usePageAssistantResult<T extends PageAssistantResult['type']>(
  type: T,
  onResult: (result: Extract<PageAssistantResult, { type: T }>) => boolean,
) {
  const pageResult = useAssistantStore((state) => state.pageResult)

  useEffect(() => {
    if (!pageResult || pageResult.type !== type) return
    const handled = onResult(pageResult as Extract<PageAssistantResult, { type: T }>)
    if (handled) {
      useAssistantStore.getState().setPageResult(null)
    }
  }, [pageResult, type, onResult])
}
