/**
 * 日内业务时间线坐标系（纯函数，可测）：09:25—18:35 映射到逻辑分析仪
 * 波形区 x∈[150,345]；时间一律转北京墙钟（领域日历语义，走 utils/beijing）。
 */
import dayjs from 'dayjs'

import { toBeijing } from '@/utils/beijing'

/** 时间轴起点 09:25（集合竞价后）、终点 18:35（盘后复盘），北京分钟数。 */
export const DAY_START_MIN = 9 * 60 + 25
export const DAY_END_MIN = 18 * 60 + 35

const X0 = 150
const X1 = 345

/** 北京分钟数 → 波形区 x（越界钳制）。 */
export function minutesToX(minutes: number): number {
  const clamped = Math.min(Math.max(minutes, DAY_START_MIN), DAY_END_MIN)
  return X0 + ((clamped - DAY_START_MIN) / (DAY_END_MIN - DAY_START_MIN)) * (X1 - X0)
}

/** ISO 时间串 → 北京墙钟当日分钟数（如 09:30 → 570）；解析失败返回 null。 */
export function beijingMinutes(iso: string): number | null {
  const d = toBeijing(dayjs(iso))
  if (!d.isValid()) return null
  return d.hour() * 60 + d.minute()
}

/** 业务日程刻度（实线=已过 / 虚线=未来 由渲染端按 nowMin 判定）。 */
export const DAY_TICKS: ReadonlyArray<{ label: string; min: number }> = [
  { label: '09:30', min: 9 * 60 + 30 },
  { label: '10:20', min: 10 * 60 + 20 },
  { label: '11:30', min: 11 * 60 + 30 },
  { label: '13:20', min: 13 * 60 + 20 },
  { label: '15:00', min: 15 * 60 },
  { label: '18:35', min: 18 * 60 + 35 },
]

export interface PulseGroup {
  x: number
  count: number
}

/** 分钟点列 → 脉冲块（相邻 <7px 合并，密度=工作节奏）。 */
export function groupPulses(minutes: number[]): PulseGroup[] {
  const xs = [...new Set(minutes.map((m) => Math.round(minutesToX(m))))].sort((a, b) => a - b)
  const groups: PulseGroup[] = []
  for (const x of xs) {
    const last = groups[groups.length - 1]
    if (last && x - last.x < 7) last.count += 1
    else groups.push({ x, count: 1 })
  }
  return groups
}
