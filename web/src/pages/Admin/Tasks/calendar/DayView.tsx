/** 日视图：单日纵向时间轴（06:00-22:00）+ 窗外任务脚注，支持月视图下钻。 */

import { Typography } from 'antd'

import { CalChip } from './CalChip'
import {
  HOURS,
  DOW_ZH,
  buildDayRows,
  formatHourLabel,
  outOfRangeNotes,
  todayBj,
  type CalendarTask,
} from './calendarUtils'

const MAX_VISIBLE_CHIPS = 8

interface DayViewProps {
  tasks: CalendarTask[]
  date: ReturnType<typeof todayBj>
  onOpen: (taskKey: string) => void
}

export function DayView({ tasks, date, onOpen }: DayViewProps) {
  const rows = buildDayRows(tasks, date)
  const notes = outOfRangeNotes(tasks, date.day())

  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs text-[#8a8f98]">
        {date.format('YYYY-MM-DD')} {DOW_ZH[date.day()]}
      </div>
      <div className="flex flex-col gap-0.5">
        {HOURS.map((hour) => {
          const entries = rows.get(hour) ?? []
          const visible = entries.slice(0, MAX_VISIBLE_CHIPS)
          const extra = entries.slice(MAX_VISIBLE_CHIPS)
          return (
            <div key={hour} className="flex items-start gap-2">
              <div className="w-10 shrink-0 pt-0.5 text-right text-[11px] text-[#8a8f98]">
                {formatHourLabel(hour)}
              </div>
              <div className="flex min-h-7 flex-1 flex-wrap content-start gap-1 rounded border border-white/[0.06] p-1">
                {visible.map((entry) => (
                  <CalChip key={`${entry.task.key}-${entry.min}`} entry={entry} onOpen={onOpen} />
                ))}
                {extra.length > 0 && (
                  <span className="self-center text-[10px] text-[#8a8f98]">
                    +{extra.length}
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {notes.length > 0 && (
        <Typography.Text type="secondary" className="text-[11px]">
          另有：{notes.join('；')}（06:00–22:00 范围外）
        </Typography.Text>
      )}
    </div>
  )
}
