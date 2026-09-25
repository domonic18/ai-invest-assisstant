import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { runCollectorTask } from '@/api/collectorAdmin'
import { fetchFinancialHealth } from '@/api/financial'
import { queryKeys } from './queryKeys'

const POLL_INTERVAL = 3_000
const POLL_TIMEOUT = 90_000

/**
 * 触发单只个股的财务三表补采，并通过轮询等待数据落库。
 *
 * 流程：
 * 1. POST /admin/collector/tasks/financial-statement/run symbols=[code]，触发采集任务
 * 2. 每 3s 拉取一次 /financial/{code}，reportDate 非空（任一报表有数据）即成功并刷新缓存
 * 3. 90s 仍未拿到数据则抛错（采集可能仍在后台跑，前端只是放弃等待）
 * 4. 组件卸载时中止轮询与在途请求
 */
export function useCollectStockFinancial(code: string) {
  const queryClient = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  return useMutation({
    mutationFn: async () => {
      const controller = new AbortController()
      abortRef.current = controller

      await runCollectorTask('financial-statement', { symbols: [code] })

      const startedAt = Date.now()
      while (Date.now() - startedAt < POLL_TIMEOUT) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL))
        if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError')
        const health = await fetchFinancialHealth(code)
        if (health.reportDate) {
          queryClient.setQueryData([...queryKeys.financial.all, code, undefined], health)
          queryClient.invalidateQueries({ queryKey: ['financial'] })
          queryClient.invalidateQueries({ queryKey: ['financial-history', code] })
          return
        }
      }
      throw new Error('采集超时：任务已提交但未在 90 秒内完成，请稍后刷新查看')
    },
  })
}
