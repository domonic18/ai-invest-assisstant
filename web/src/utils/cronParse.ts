/**
 * 5 字段 cron 解析层：字段展开、合法性校验、结构化解析。
 * cron 小时语义为北京时间（collector_task 约定）；解析失败一律返回 null，
 * 调用方优雅回退（cronstrue 长句 / 原始表达式）。排程计算见 cronSchedule，
 * 中文释义见 cronFormat，入口经 utils/cron barrel。
 */

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

/** 展开 cron 字段：支持 `*`、步进（`星号/n`）、`a-b`、`a-b/n`、`a,b,c`。 */
export function cronExpand(field: string, lo: number, hi: number): number[] {
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

export function parseField(field: string, lo: number, hi: number): number[] | null {
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
