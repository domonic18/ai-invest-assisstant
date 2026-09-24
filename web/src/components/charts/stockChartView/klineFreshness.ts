/** 日 K 新鲜度判定（纯函数）。口径与后端 kline_freshness 采集器一致：
 * 当日 bar 收盘后存在发布滞后，17:00 前不认为「期望日=今天」的落后是异常。 */

import dayjs from 'dayjs'

import { toBeijing } from '@/utils/beijing'

const PUBLISH_READY_MINUTES = 17 * 60

/** 上海时区（北京墙钟）的当前日历日（YYYY-MM-DD）与当日分钟数。 */
export function shanghaiNow(now: Date = new Date()): { date: string; minutes: number } {
  const t = toBeijing(dayjs(now))
  return {
    date: t.format('YYYY-MM-DD'),
    minutes: t.hour() * 60 + t.minute(),
  }
}

/** 最后一根 bar 是否落后于最近交易日（ISO 日期可直接字典序比较）。 */
export function isKlineBehind(lastBarDate?: string, latestTradeDate?: string): boolean {
  return lastBarDate !== undefined && latestTradeDate !== undefined && lastBarDate < latestTradeDate
}

/** 期望日不早于今天且未过 17:00 发布窗口：当日 bar 尚未发布属正常状态，不触发补采。 */
export function isPublishPending(latestTradeDate?: string, now: Date = new Date()): boolean {
  if (latestTradeDate === undefined) return false
  const cn = shanghaiNow(now)
  return latestTradeDate >= cn.date && cn.minutes < PUBLISH_READY_MINUTES
}
