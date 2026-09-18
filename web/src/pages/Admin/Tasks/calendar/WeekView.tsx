/** 周视图：通用周 7 列 × 小时行（06:00-22:00），高频任务聚合为带状 chip。 */

import { Tooltip, Typography } from 'antd'

import { CalChip } from './CalChip'
import {
  HOURS,
  WEEK_COL_LABELS,
  WEEK_COLS,
  buildWeekCells,
  formatHourLabel,
  outOfRangeNotes,
  type CalendarTask,
} from './calendarUtils'

const MAX_VISIBLE_CHIPS = 6

interface WeekViewProps {
  tasks: CalendarTask[]
  onOpen: (taskKey: string) => void
}

export function WeekView({ tasks, onOpen }: WeekViewProps) {
  const cells = buildWeekCells(tasks)
  const notes = outOfRangeNotes(tasks)

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto">
        <div
          className="grid min-w-[860px] gap-px"
          style={{ gridTemplateColumns: '56px repeat(7, minmax(112px, 1fr))' }}
        >
          <div />
          {WEEK_COL_LABELS.map((label) => (
            <div
              key={label}
              className="py-1.5 text-center text-xs font-medium text-[#8a8f98]"
            >
              周{label}
            </div>
          ))}
          {HOURS.map((hour) => (
            <div key={hour} className="contents">
              <div className="pr-2 text-right text-[11px] leading-7 text-[#8a8f98]">
                {formatHourLabel(hour)}
              </div>
              {WEEK_COLS.map((dow) => {
                const entries = cells.get(dow)?.get(hour) ?? []
                const visible = entries.slice(0, MAX_VISIBLE_CHIPS)
                const extra = entries.slice(MAX_VISIBLE_CHIPS)
                return (
                  <div
                    key={`${dow}-${hour}`}
                    className="flex min-h-7 flex-col gap-0.5 rounded border border-white/[0.06] p-0.5"
                  >
                    {visible.map((entry) => (
                      <CalChip key={`${entry.task.key}-${entry.min}`} entry={entry} onOpen={onOpen} />
                    ))}
                    {extra.length > 0 && (
                      <Tooltip
                        title={extra.map((e) => e.task.label).join('、')}
                      >
                        <span className="cursor-help text-[10px] text-[#8a8f98]">
                          +{extra.length}
                        </span>
                      </Tooltip>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
      {notes.length > 0 && (
        <Typography.Text type="secondary" className="text-[11px]">
          另有：{notes.join('；')}（06:00–22:00 范围外）
        </Typography.Text>
      )}
    </div>
  )
}
