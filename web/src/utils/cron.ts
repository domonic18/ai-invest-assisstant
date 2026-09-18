/**
 * 5 字段 cron 迷你工具：解析、紧凑中文释义、下次执行、单日 occurrence。
 * cron 小时语义为北京时间（collector_task 约定），因此全部计算固定在
 * UTC+8 墙钟上进行，不受浏览器时区影响；解析失败一律返回 null，
 * 调用方优雅回退（cronstrue 长句 / 原始表达式）。
 */

import dayjs, { type Dayjs } from 'dayjs'
import utc from 'dayjs/plugin/utc'

dayjs.extend(utc)

const BJ_OFFSET_MIN = 480

/** 分钟 occurrence 数超过该阈值视为高频任务（日历视图聚合为带状 chip）。 */
export const HIGH_FREQ_MINUTES = 6

export interface CronParsed {
  minutes: number[]
  hours: number[]
  /** 日（1-31）；`*` 为 null */
  doms: number[] | null
  /** 月（1-12）；`*` 为 null */
  months: number[] | null
  /** 周（0-6，0=周日，7 归一为 0）；`*` 为 null */
  dows: number[] | null
  /** 分钟字段步进（`星号/n` / `a-b/n`）；无步进为 null，`*` 视为步进 1 返回 1 */
  minuteStep: number | null
}

const DOW_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

/** 展开 cron 字段：支持 `*`、步进（`星号/n`）、`a-b`、`a-b/n`、`a,b,c`。 */
function cronExpand(field: string, lo: number, hi: number): number[] {
  const out: number[] = []
  for (const part of field.split(',')) {
    let step = 1
    let range = part
    const slash = part.indexOf('/')
    if (slash >= 0) {
      range = part.slice(0, slash)
      step = Number.parseInt(part.slice(slash + 1), 10) || 1
    }
    let a = lo
    let b = hi
    if (range !== '*' && range !== '') {
      const dash = range.indexOf('-')
      if (dash >= 0) {
        a = Number.parseInt(range.slice(0, dash), 10)
        b = Number.parseInt(range.slice(dash + 1), 10)
      } else {
        a = b = Number.parseInt(range, 10)
      }
    }
    if (Number.isNaN(a) || Number.isNaN(b) || step < 1) continue
    for (let v = a; v <= b; v += step) out.push(v)
  }
  return out
}

function parseField(field: string, lo: number, hi: number): number[] | null {
  if (!/^[\d*,\-/]+$/.test(field)) return null
  const values = cronExpand(field, lo, hi).filter((v) => v >= lo && v <= hi)
  const uniq = [...new Set(values)].sort((a, b) => a - b)
  return uniq.length ? uniq : null
}

export function parseCron(expr: string): CronParsed | null {
  const f = expr.trim().split(/\s+/)
  if (f.length !== 5) return null
  const minutes = parseField(f[0], 0, 59)
  const hours = parseField(f[1], 0, 23)
  if (!minutes || !hours) return null
  const doms = f[2] === '*' ? null : parseField(f[2], 1, 31)
  const months = f[3] === '*' ? null : parseField(f[3], 1, 12)
  const dows = f[4] === '*' ? null : parseField(f[4], 0, 7)
  if ((f[2] !== '*' && !doms) || (f[3] !== '*' && !months) || (f[4] !== '*' && !dows)) {
    return null
  }
  const slash = f[0].indexOf('/')
  let minuteStep: number | null = null
  if (slash >= 0) {
    minuteStep = Number.parseInt(f[0].slice(slash + 1), 10) || 1
  } else if (f[0] === '*') {
    minuteStep = 1
  }
  return {
    minutes,
    hours,
    doms,
    months,
    dows: dows ? [...new Set(dows.map((d) => d % 7))] : null,
    minuteStep,
  }
}

/** 高频任务判定（与原型一致的唯一点：展开分钟数 > 6）。 */
export function isHighFreq(p: CronParsed): boolean {
  return p.minutes.length > HIGH_FREQ_MINUTES
}

/** 标准 cron 语义：dom 与 dow 任一受限时取 OR，否则各自必须命中。 */
function dayMatches(p: CronParsed, d: Dayjs): boolean {
  if (p.months && !p.months.includes(d.month() + 1)) return false
  const domOk = !p.doms || p.doms.includes(d.date())
  const dowOk = !p.dows || p.dows.includes(d.day())
  if (p.doms && p.dows) return domOk || dowOk
  return domOk && dowOk
}

function toBeijing(d: Dayjs): Dayjs {
  return d.utcOffset(BJ_OFFSET_MIN)
}

export function bjNow(): Dayjs {
  return toBeijing(dayjs())
}

/** 该日（北京时区）的全部触发分钟数（0-1439，升序）；不命中或解析失败返回空数组/null。 */
export function runsOnDate(expr: string, date: Dayjs): number[] | null {
  const p = parseCron(expr)
  if (!p) return null
  const d = toBeijing(date)
  if (!dayMatches(p, d)) return []
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
    if (!dayMatches(p, day)) continue
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
  const dayDiff = toBeijing(t).startOf('day').diff(toBeijing(from).startOf('day'), 'day')
  const prefix = dayDiff === 0 ? '今天' : dayDiff === 1 ? '明天' : DOW_ZH[t.day()]
  return `${prefix} ${pad2(t.hour())}:${pad2(t.minute())}`
}
