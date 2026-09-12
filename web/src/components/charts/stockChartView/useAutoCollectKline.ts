import { useEffect, useRef } from 'react'

import { useCollectStockKline } from '@/hooks/useCollectStockKline'

import { isKlineBehind, isPublishPending } from './klineFreshness'

export interface UseAutoCollectKlineInput {
  /** 视图 K 线查询已完成（成功或失败均可判定） */
  ready: boolean
  /** 视图当前没有任何 K 线数据 */
  missing: boolean
  /** 最后一根 bar 日期（仅日 K 视图传；周/月聚合桶日期与交易日不可比） */
  lastBarDate?: string
  /** 交易日历权威最近交易日（仅日 K 视图传） */
  latestTradeDate?: string
}

// 双视图（日/周）共用同一条日 K 查询，模块级去重避免重复派发采集任务
const inFlightCodes = new Set<string>()

/**
 * 个股 K 线缺数据或落后最近交易日时自动补采，免去手动点击：
 * - 缺数据 → 立即补采（轮询非空即成功）
 * - 落后 → 补采并轮询至期望日 bar 出现；「期望日=今天且未过 17:00 发布窗口」视为正常，静默
 * - 每个 code 只自动触发一次，失败后降级为界面上的手动重试
 */
export function useAutoCollectKline(code: string, { ready, missing, lastBarDate, latestTradeDate }: UseAutoCollectKlineInput) {
  const collect = useCollectStockKline(code)
  const { mutateAsync, isPending } = collect
  const attemptedRef = useRef<string | null>(null)

  const behind = !missing && isKlineBehind(lastBarDate, latestTradeDate)
  const suppressed = behind && isPublishPending(latestTradeDate)

  useEffect(() => {
    if (!ready || attemptedRef.current === code || isPending) return
    const shouldFire = missing || (behind && !suppressed)
    if (!shouldFire || inFlightCodes.has(code)) return
    attemptedRef.current = code
    inFlightCodes.add(code)
    mutateAsync(missing ? undefined : latestTradeDate)
      .catch(() => {})
      .finally(() => inFlightCodes.delete(code))
  }, [ready, missing, behind, suppressed, code, latestTradeDate, mutateAsync, isPending])

  return { collect, behind, suppressed }
}
