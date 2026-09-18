/** 任务日历三视图（周/日/月）共用的任务解析与 occurrence 聚合。 */

import type { Dayjs } from 'dayjs'

import type { AdminTask } from '@ai-invest/shared'

import { getTaskLabel } from '@/utils/collectorTaskLabels'
import { bjDayMatches, bjNow, toBeijing } from '@/utils/beijing'
import { cronZh, isHighFreq, parseCron, type CronParsed } from '@/utils/cron'
import { taskCategoryColor, taskCategoryLabel, taskCategoryOf } from '@/utils/taskCategoryMeta'

/** 日历可见时间窗（盘前到盘后），窗外任务汇总为脚注。 */
export const HOUR_START = 6
export const HOUR_END = 22
export const HOURS = Array.from(
  { length: HOUR_END - HOUR_START + 1 },
  (_, i) => HOUR_START + i,
)
/** 网格列序：周一..周日（JS day: 1..6, 0）。 */
export const WEEK_COLS = [1, 2, 3, 4, 5, 6, 0]
export const WEEK_COL_LABELS = ['一', '二', '三', '四', '五', '六', '日']
export const DOW_ZH = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

export interface CalendarTask {
  key: string
  label: string
  name: string
  category: string
  schedule: string
  parsed: CronParsed
  isHighFreq: boolean
  zh: string | null
}

/** 由任务列表构建可渲染的日历任务（仅保留 schedule 可解析的行）。 */
export function buildCalendarTasks(tasks: AdminTask[]): CalendarTask[] {
  const out: CalendarTask[] = []
  for (const task of tasks) {
    if (!task.schedule) continue
    const parsed = parseCron(task.schedule)
    if (!parsed) continue
    out.push({
      key: String(task.id),
      label: getTaskLabel(task.taskType),
      name: task.taskName,
      category: taskCategoryOf(task.taskType),
      schedule: task.schedule,
      parsed,
      isHighFreq: isHighFreq(parsed),
      zh: cronZh(task.schedule),
    })
  }
  return out
}

export interface CalEntry {
  min: number
  task: CalendarTask
  band: boolean
}

function isOutsideHours(p: CronParsed): boolean {
  return p.hours.every((h) => h < HOUR_START || h > HOUR_END)
}

/** 周视图为通用周（不绑定具体日期）：dom 受限任务按 dow 命中近似显示，日/月视图为精确判定。 */
export function taskShowsOnDow(task: CalendarTask, jsDow: number): boolean {
  return !task.parsed.dows || task.parsed.dows.includes(jsDow)
}

export function taskShowsOnDate(task: CalendarTask, date: Dayjs): boolean {
  return bjDayMatches(task.parsed, toBeijing(date))
}

function pushEntries(
  target: CalEntry[],
  task: CalendarTask,
): void {
  if (task.isHighFreq) {
    target.push({ min: 0, task, band: true })
    return
  }
  for (const m of task.parsed.minutes) target.push({ min: m, task, band: false })
}

/** 周视图：dow → hour → 按分钟排序的 entries。 */
export function buildWeekCells(
  tasks: CalendarTask[],
): Map<number, Map<number, CalEntry[]>> {
  const cells = new Map<number, Map<number, CalEntry[]>>()
  for (const task of tasks) {
    for (const dow of WEEK_COLS) {
      if (!taskShowsOnDow(task, dow)) continue
      for (const h of task.parsed.hours) {
        if (h < HOUR_START || h > HOUR_END) continue
        let byHour = cells.get(dow)
        if (!byHour) {
          byHour = new Map()
          cells.set(dow, byHour)
        }
        const arr = byHour.get(h) ?? []
        pushEntries(arr, task)
        byHour.set(h, arr)
      }
    }
  }
  for (const byHour of cells.values()) {
    for (const [h, arr] of byHour) byHour.set(h, arr.sort((a, b) => a.min - b.min))
  }
  return cells
}

/** 日视图：hour → 按分钟排序的 entries。 */
export function buildDayRows(tasks: CalendarTask[], date: Dayjs): Map<number, CalEntry[]> {
  const rows = new Map<number, CalEntry[]>()
  for (const task of tasks) {
    if (!taskShowsOnDate(task, date)) continue
    for (const h of task.parsed.hours) {
      if (h < HOUR_START || h > HOUR_END) continue
      const arr = rows.get(h) ?? []
      pushEntries(arr, task)
      rows.set(h, arr)
    }
  }
  for (const [h, arr] of rows) rows.set(h, arr.sort((a, b) => a.min - b.min))
  return rows
}

/** 06:00-22:00 窗外任务脚注（可选限定某日）。 */
export function outOfRangeNotes(tasks: CalendarTask[], jsDow?: number): string[] {
  const notes: string[] = []
  for (const task of tasks) {
    if (jsDow !== undefined && !taskShowsOnDow(task, jsDow)) continue
    if (isOutsideHours(task.parsed)) {
      notes.push(`${task.label} ${task.zh ?? task.schedule}`)
    }
  }
  return notes
}

export interface MonthCell {
  date: Dayjs
  jsDow: number
  matched: CalendarTask[]
  dots: { category: string; color: string; label: string; count: number }[]
}

/** 月视图：每格当日「任务种数」（去重）+ 业务分类密度点。 */
export function buildMonthCells(
  tasks: CalendarTask[],
  monthStart: Dayjs,
): MonthCell[] {
  const cells: MonthCell[] = []
  const days = monthStart.daysInMonth()
  for (let dd = 1; dd <= days; dd++) {
    const date = monthStart.date(dd)
    const matched = tasks.filter((t) => taskShowsOnDate(t, date))
    const byCategory = new Map<string, number>()
    for (const t of matched) {
      byCategory.set(t.category, (byCategory.get(t.category) ?? 0) + 1)
    }
    const dots = [...byCategory.entries()]
      .map(([category, count]) => ({
        category,
        color: taskCategoryColor(category),
        label: taskCategoryLabel(category),
        count,
      }))
      .sort((a, b) => b.count - a.count)
    cells.push({ date, jsDow: date.day(), matched, dots })
  }
  return cells
}

/** hex → rgba 背景（chip 半透明底色）。 */
export function withAlpha(hex: string, alpha: number): string {
  const v = Number.parseInt(hex.slice(1), 16)
  return `rgba(${(v >> 16) & 255}, ${(v >> 8) & 255}, ${v & 255}, ${alpha})`
}

export function formatHourLabel(h: number): string {
  return `${String(h).padStart(2, '0')}:00`
}

export function formatMinute(min: number): string {
  return `${String(Math.floor(min / 60)).padStart(2, '0')}:${String(min % 60).padStart(2, '0')}`
}

/** 当前北京时间的今天（供日视图默认日期）。 */
export function todayBj(): Dayjs {
  return bjNow()
}
