/**
 * 5 字段 cron 中文释义层：紧凑中文释义、下次执行标签。
 * 解析层见 cronParse，排程计算见 cronSchedule，入口经 utils/cron barrel；
 * 解析失败一律返回 null，调用方优雅回退（cronstrue 长句 / 原始表达式）。
 */

import type { Dayjs } from 'dayjs'

import { bjNow, toBeijing } from './beijing'
import { parseField } from './cronParse'

const DOW_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

/** 紧凑中文释义：「工作日 16:30」「工作日 09–15 每 5 分钟」「每天 08:00、18:30」。 */
export function cronZh(expr: string | null | undefined): string | null {
  if (!expr) return null
  const f = expr.trim().split(/\s+/)
  if (f.length !== 5) return null
  // dom/month 受限的复杂表达式不做紧凑释义，交给 cronstrue
  if (f[2] !== '*' || f[3] !== '*') return null

  let day = '每天'
  if (f[4] === '1-5') day = '工作日'
  else if (f[4] === '2-6') day = '周二至周六'
  else if (f[4] !== '*') {
    const dows = parseField(f[4], 0, 7)
    if (!dows) return null
    day = dows.map((d) => DOW_ZH[d % 7]).join('、')
  }

  let band: string | null = null
  if (f[0].includes('/')) {
    const step = Number.parseInt(f[0].split('/')[1], 10) || 1
    band = `每 ${step} 分钟`
  } else if (f[0] === '*') {
    band = '每分钟'
  }

  let hourZh = ''
  if (f[1].includes('-')) {
    const [a, b] = f[1].split('-')
    hourZh = `${pad2(Number(a))}–${pad2(Number(b))} `
  } else if (f[1] !== '*') {
    hourZh = `${pad2(Number(f[1]))} 时 `
  }
  if (band) return day + ' ' + hourZh + band

  const minutes = parseField(f[0], 0, 59)
  const hours = parseField(f[1], 0, 23)
  if (!minutes || !hours) return null
  const times: string[] = []
  for (const h of hours) {
    for (const m of minutes) times.push(`${pad2(h)}:${pad2(m)}`)
  }
  times.sort()
  return day + ' ' + times.slice(0, 6).join('、') + (times.length > 6 ? ' 等' : '')
}

/** 下次执行标签：「今天 16:30」「明天 09:00」「周四 18:35」。 */
export function formatNextRunLabel(t: Dayjs, from: Dayjs = bjNow()): string {
  const tBj = toBeijing(t)
  const dayDiff = tBj.startOf('day').diff(toBeijing(from).startOf('day'), 'day')
  const prefix = dayDiff === 0 ? '今天' : dayDiff === 1 ? '明天' : DOW_ZH[tBj.day()]
  return `${prefix} ${pad2(tBj.hour())}:${pad2(tBj.minute())}`
}
