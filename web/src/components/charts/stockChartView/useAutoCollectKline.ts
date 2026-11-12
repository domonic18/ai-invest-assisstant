import { useEffect, useMemo, useRef } from 'react'

import { useCollectStockKline } from '@/hooks/useCollectStockKline'
import type { CollectKlineTarget } from '@/hooks/useCollectStockKline'

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
  /** 库内历史被截断（后端判定，需补全历史） */
  insufficient?: boolean
  /** 健康历史的最少根数（后端给出，避免两端常量漂移） */
  minHealthyBars?: number
  /** 当前最早 bar 日期（depth 达标判据之一：历史起点前移） */
  firstBarDate?: string
}

// 后端未给出阈值时的兜底（与后端 MIN_HEALTHY_BARS 同值）
const DEFAULT_MIN_HEALTHY_BARS = 60

// 双视图（日/周）共用同一条日 K 查询，模块级去重避免重复派发采集任务
const inFlightCodes = new Set<string>()

/**
 * 个股 K 线缺数据、历史过浅或落后最近交易日时自动补采，免去手动点击：
 * - 缺数据 → 立即补采（轮询非空即成功）
 * - 历史过浅 → 补采全历史（轮询至 bar 数达标或历史起点前移）
 * - 落后 → 补采并轮询至期望日 bar 出现；「期望日=今天且未过 17:00 发布窗口」视为正常，静默
 * - 每个 code 只自动触发一次，失败后降级为界面上的手动重试
 */
export function useAutoCollectKline(
  code: string,
  {
    ready,
    missing,
    lastBarDate,
    latestTradeDate,
    insufficient,
    minHealthyBars,
    firstBarDate,
  }: UseAutoCollectKlineInput,
) {
  const collect = useCollectStockKline(code)
  const { mutateAsync, isPending } = collect
  const attemptedRef = useRef<string | null>(null)

  const behind = !missing && isKlineBehind(lastBarDate, latestTradeDate)
  const suppressed = behind && isPublishPending(latestTradeDate)
  const truncated = !missing && insufficient === true

  const target = useMemo<CollectKlineTarget | null>(() => {
    if (behind && !suppressed && latestTradeDate) {
      return { mode: 'freshness', notBefore: latestTradeDate }
    }
    if (truncated) {
      return {
        mode: 'depth',
        minBars: minHealthyBars ?? DEFAULT_MIN_HEALTHY_BARS,
        beforeFirstBarDate: firstBarDate,
      }
    }
    if (missing) return { mode: 'empty' }
    return null
  }, [behind, suppressed, latestTradeDate, truncated, minHealthyBars, firstBarDate, missing])

  useEffect(() => {
    if (!ready || attemptedRef.current === code || isPending) return
    if (!target || inFlightCodes.has(code)) return
    attemptedRef.current = code
    inFlightCodes.add(code)
    mutateAsync(target)
      .catch(() => {})
      .finally(() => inFlightCodes.delete(code))
  }, [ready, code, target, mutateAsync, isPending])

  return { collect, behind, suppressed, truncated }
}
