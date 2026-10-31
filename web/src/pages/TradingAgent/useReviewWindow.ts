/** 复盘窗口状态：周期/作用域/基准日/自定义区间 → 读取与生成共用的请求窗口。 */

import type { Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'

import type {
  TradingAgentReviewWindow,
  TradingReviewPeriod,
  TradingReviewScope,
} from '@ai-invest/shared'

import { useTradingAgentDates } from '@/hooks/useTradingAgent'
import { DATE_FORMAT } from '@/utils/formatters'

import { CUSTOM_RANGE_TOO_LONG, isRangeTooLong } from './reviewMeta'

export interface ReviewWindowState {
  period: TradingReviewPeriod
  scope: TradingReviewScope
  selectedDate: Dayjs | null
  range: [Dayjs, Dayjs] | null
  /** 日历打点（已生成复盘的基准日，按周期）。 */
  dates: ReturnType<typeof useTradingAgentDates>['data']
  /** 读取/生成/对比共用窗口：range 优先，缺省按周期 + 作用域 + 基准日。 */
  window: TradingAgentReviewWindow
  rangeWarning: string | null
  selectedTradeDate: string | undefined
  changePeriod: (next: TradingReviewPeriod) => void
  changeScope: (next: TradingReviewScope) => void
  setSelectedDate: (value: Dayjs | null) => void
  setRange: (value: [Dayjs, Dayjs] | null) => void
}

export function useReviewWindow(agentKey: string): ReviewWindowState {
  const [period, setPeriod] = useState<TradingReviewPeriod>('day')
  const [scope, setScope] = useState<TradingReviewScope>('current')
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(null)
  const [range, setRange] = useState<[Dayjs, Dayjs] | null>(null)
  const { data: dates } = useTradingAgentDates(agentKey)

  const window = useMemo<TradingAgentReviewWindow>(() => {
    if (range) {
      return {
        startDate: range[0].format(DATE_FORMAT),
        endDate: range[1].format(DATE_FORMAT),
      }
    }
    return {
      period,
      scope,
      tradeDate: selectedDate?.format(DATE_FORMAT),
    }
  }, [range, period, scope, selectedDate])

  const changePeriod = (next: TradingReviewPeriod) => {
    setPeriod(next)
    // 周期切换清日期与区间：旧窗口对新周期通常无对应记录
    setSelectedDate(null)
    setRange(null)
    setScope('current')
  }

  const changeScope = (next: TradingReviewScope) => {
    setScope(next)
    setSelectedDate(null)
  }

  return {
    period,
    scope,
    selectedDate,
    range,
    dates,
    window,
    rangeWarning:
      range && isRangeTooLong(range[0], range[1]) ? CUSTOM_RANGE_TOO_LONG : null,
    selectedTradeDate: selectedDate?.format(DATE_FORMAT),
    changePeriod,
    changeScope,
    setSelectedDate,
    setRange,
  }
}
