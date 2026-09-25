/**
 * 5 字段 cron 排程计算层：单日 occurrence 展开、未来 n 次触发时间。
 * 全部计算经 utils/beijing 固定在 UTC+8 墙钟上，不受浏览器时区影响；
 * 解析层见 cronParse，中文释义见 cronFormat，入口经 utils/cron barrel。
 */

import type { Dayjs } from 'dayjs'

import { bjDayMatches, bjNow, toBeijing } from './beijing'
import { parseCron } from './cronParse'

/** 该日（北京时区）的全部触发分钟数（0-1439，升序）；不命中或解析失败返回空数组/null。 */
export function runsOnDate(expr: string, date: Dayjs): number[] | null {
  const p = parseCron(expr)
  if (!p) return null
  const d = toBeijing(date)
  if (!bjDayMatches(p, d)) return []
  const out: number[] = []
  for (const h of p.hours) {
    for (const m of p.minutes) out.push(h * 60 + m)
  }
  return out.sort((a, b) => a - b)
}

/** 未来 n 次触发时间（北京墙钟）；解析失败返回 null，找不到则返回不足 n 的数组。 */
export function nextRuns(expr: string, count: number, from: Dayjs = bjNow()): Dayjs[] | null {
  const p = parseCron(expr)
  if (!p) return null
  const out: Dayjs[] = []
  const start = toBeijing(from)
  const times = runsOnDate(expr, start)?.map((mod) => start.startOf('day').add(mod, 'minute')) ?? []
  for (const t of times) {
    if (out.length >= count) break
    if (t.isAfter(start)) out.push(t)
  }
  for (let d = 1; d < 366 && out.length < count; d++) {
    const day = start.startOf('day').add(d, 'day')
    if (!bjDayMatches(p, day)) continue
    for (const h of p.hours) {
      for (const m of p.minutes) {
        if (out.length >= count) break
        out.push(day.hour(h).minute(m))
      }
      if (out.length >= count) break
    }
  }
  return out.slice(0, count)
}
