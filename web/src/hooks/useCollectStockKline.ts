import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { runCollectorTask } from '@/api/collectorAdmin'
import { fetchStockKline } from '@/api/stocks'
import { queryKeys } from './queryKeys'

const POLL_INTERVAL = 3_000
const POLL_TIMEOUT = 90_000

/**
 * 触发单只个股的 K 线补采，并通过轮询等待数据落库。
 *
 * 流程：
 * 1. POST /admin/collector/tasks/kline/run symbols=[code]，触发采集任务
 * 2. 每 3s 拉取一次 /stocks/{code}/kline，命中非空即视为成功并刷新缓存
 * 3. 90s 仍未拿到数据则抛错（采集可能仍在后台跑，前端只是放弃等待）
 * 4. 组件卸载时中止轮询与在途请求
 */
export function useCollectStockKline(code: string) {
  const queryClient = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  return useMutation({
    mutationFn: async () => {
      const controller = new AbortController()
      abortRef.current = controller

      await runCollectorTask('kline', { symbols: [code], period: 'daily' })

      const startedAt = Date.now()
      while (Date.now() - startedAt < POLL_TIMEOUT) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL))
        if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError')
        const kline = await fetchStockKline(code, {
          period: 'daily',
          limit: 250,
          signal: controller.signal,
        })
        if (kline.bars.length > 0) {
          queryClient.setQueryData(queryKeys.stocks.kline(code, 'daily', 250), kline)
          queryClient.invalidateQueries({ queryKey: ['stocks', 'kline', code] })
          return
        }
      }
      throw new Error('采集超时：任务已提交但未在 90 秒内完成，请稍后刷新查看')
    },
  })
}
