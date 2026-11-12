import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { runCollectorTask } from '@/api/collectorAdmin'
import { fetchStockKline } from '@/api/stocks'
import { queryKeys } from './queryKeys'

const POLL_INTERVAL = 3_000
const POLL_TIMEOUT = 90_000

/**
 * 补采目标（决定轮询的达标判据）：
 * - empty：库内无数据，出现任意一根 bar 即达标
 * - freshness：补到期望交易日（notBefore）为止
 * - depth：补足历史深度，bar 数达 minBars 或历史起点前移即达标
 */
export type CollectKlineTarget =
  | { mode: 'empty' }
  | { mode: 'freshness'; notBefore: string }
  | { mode: 'depth'; minBars: number; beforeFirstBarDate?: string }

interface KlineSnapshot {
  bars: { date: string }[]
}

function isTargetReached(kline: KlineSnapshot, target: CollectKlineTarget): boolean {
  const { bars } = kline
  if (target.mode === 'empty') return bars.length > 0
  if (target.mode === 'depth') {
    if (bars.length >= target.minBars) return true
    const firstBarDate = bars[0]?.date
    return (
      target.beforeFirstBarDate !== undefined &&
      firstBarDate !== undefined &&
      firstBarDate < target.beforeFirstBarDate
    )
  }
  const lastBarDate = bars[bars.length - 1]?.date
  return bars.length > 0 && (lastBarDate ?? '') >= target.notBefore
}

/**
 * 触发单只个股的 K 线补采，并通过轮询等待数据落库。
 *
 * 流程：
 * 1. POST /admin/collector/tasks/kline/run symbols=[code]，触发采集任务
 *    （该任务按标的取全量历史，一次运行即可补齐被截断的历史）
 * 2. 每 3s 拉取一次 /stocks/{code}/kline，按 target 判据判定达标并刷新缓存
 * 3. 90s 仍未达标则抛错（采集可能仍在后台跑，前端只是放弃等待）
 * 4. 组件卸载时中止轮询与在途请求
 */
export function useCollectStockKline(code: string) {
  const queryClient = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  return useMutation({
    mutationFn: async (target: CollectKlineTarget) => {
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
        if (isTargetReached(kline, target)) {
          queryClient.setQueryData(queryKeys.stocks.kline(code, 'daily', 250), kline)
          queryClient.invalidateQueries({ queryKey: ['stocks', 'kline', code] })
          return
        }
      }
      throw new Error('采集超时：任务已提交但未在 90 秒内完成，请稍后刷新查看')
    },
  })
}
