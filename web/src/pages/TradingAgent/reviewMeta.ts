/** 复盘周期展示元数据与窗口文案（六档周期、快捷作用域）。 */

import dayjs from 'dayjs'

import type {
  TradingReviewPeriod,
  TradingReviewScope,
  TradingAgentReviewWindow,
} from '@ai-invest/shared'

export const REVIEW_PERIOD_LABELS: Record<TradingReviewPeriod, string> = {
  day: '日',
  week: '周',
  month: '月',
  quarter: '季',
  half_year: '半年',
  year: '年',
}

export const REVIEW_PERIOD_OPTIONS = (
  Object.keys(REVIEW_PERIOD_LABELS) as TradingReviewPeriod[]
).map((value) => ({ label: REVIEW_PERIOD_LABELS[value], value }))

/** 定时任务自动生成的周期（日/周/月）；季/半年/年按需生成。 */
export const AUTO_REVIEW_PERIODS: readonly TradingReviewPeriod[] = ['day', 'week', 'month']

/** 与后端 `CUSTOM_RANGE_TOO_LONG` 同文案（生成前的前端提示；生成后后端 notes 也会带）。 */
export const CUSTOM_RANGE_TOO_LONG = '自定义区间跨度超过 12 个月，建议使用年档查看完整年度复盘'

/** 自定义区间是否超过 12 个月（与后端映射口径一致：end > start + 12 月）。 */
export function isRangeTooLong(start: dayjs.Dayjs, end: dayjs.Dayjs): boolean {
  return end.isAfter(start.add(12, 'month'), 'day')
}

/** 窗口的人话描述（对比弹窗里展示当前窗口）。 */
export function describeWindow(window: TradingAgentReviewWindow): string {
  if (window.startDate && window.endDate) return `${window.startDate} ~ ${window.endDate}`
  const period = window.period ? REVIEW_PERIOD_LABELS[window.period] : '复盘'
  const scope: TradingReviewScope = window.scope ?? 'current'
  const scopeText = scope === 'previous' ? '上期' : '本期'
  const dateText = window.tradeDate ? `（基准日 ${window.tradeDate}）` : ''
  return `${period}${scopeText}${dateText}`
}
