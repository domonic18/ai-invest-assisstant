import { useEffect, useRef } from 'react'

import { useCollectStockFinancial } from './useCollectStockFinancial'

export interface UseAutoCollectFinancialInput {
  /** 财务查询已完成（成功或失败均可判定） */
  ready: boolean
  /** 当前没有任何报表数据（reportDate 为空） */
  missing: boolean
}

// 与 useAutoCollectKline 同一去重约定：多处挂载/重复渲染不重复派发采集任务
const inFlightCodes = new Set<string>()

/**
 * 个股财务三表缺失时自动补采（对齐 K 线缺数据自动补采的行为）：
 * - 仅在用户打开财务分区且数据缺失时触发一次
 * - 失败后降级为界面上的手动重试
 */
export function useAutoCollectFinancial(code: string, { ready, missing }: UseAutoCollectFinancialInput) {
  const collect = useCollectStockFinancial(code)
  const { mutateAsync, isPending } = collect
  const attemptedRef = useRef<string | null>(null)

  useEffect(() => {
    if (!ready || !missing || attemptedRef.current === code || isPending) return
    if (inFlightCodes.has(code)) return
    attemptedRef.current = code
    inFlightCodes.add(code)
    mutateAsync()
      .catch(() => {})
      .finally(() => inFlightCodes.delete(code))
  }, [ready, missing, code, mutateAsync, isPending])

  return { collect }
}
