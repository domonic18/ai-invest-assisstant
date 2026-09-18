/** 月视图：月历格展示当日任务种数 + 数据类型密度点，点击下钻日视图。 */

import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { Button, Typography } from 'antd'
import type { Dayjs } from 'dayjs'

import {
  buildMonthCells,
  todayBj,
  type CalendarTask,
} from './calendarUtils'

interface MonthViewProps {
  tasks: CalendarTask[]
  month: Dayjs
  onMonthChange: (month: Dayjs) => void
  onDrillDay: (date: Dayjs) => void
}

const LEAD_LABELS = ['一', '二', '三', '四', '五', '六', '日']

export function MonthView({ tasks, month, onMonthChange, onDrillDay }: MonthViewProps) {
  const cells = buildMonthCells(tasks, month.startOf('month'))
  const firstDow = cells[0]?.jsDow ?? 1
  const lead = (firstDow + 6) % 7
  const today = todayBj()

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-center gap-3">
        <Button
          size="small"
          type="text"
          icon={<LeftOutlined />}
          onClick={() => onMonthChange(month.subtract(1, 'month'))}
        />
        <span className="text-sm font-medium">{month.format('YYYY-MM')}</span>
        <Button
          size="small"
          type="text"
          icon={<RightOutlined />}
          onClick={() => onMonthChange(month.add(1, 'month'))}
        />
      </div>

      <div className="grid grid-cols-7 gap-1">
        {LEAD_LABELS.map((label) => (
          <div key={label} className="pb-1 text-center text-xs text-[#8a8f98]">
            {label}
          </div>
        ))}
        {Array.from({ length: lead }, (_, i) => (
          <div key={`lead-${i}`} />
        ))}
        {cells.map((cell) => {
          const isWeekend = cell.jsDow === 0 || cell.jsDow === 6
          const isToday = cell.date.isSame(today, 'day')
          return (
            <button
              key={cell.date.date()}
              type="button"
              onClick={() => onDrillDay(cell.date)}
              className={`flex min-h-20 cursor-pointer flex-col gap-1 rounded-md border p-1.5 text-left transition-colors hover:bg-white/[0.04] ${
                isWeekend ? 'border-white/[0.04] bg-white/[0.02]' : 'border-white/10'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-[#8a8f98]">
                  {month.format('M')}-{String(cell.date.date()).padStart(2, '0')}
                </span>
                {isToday && (
                  <span className="rounded bg-[rgba(94,106,210,0.25)] px-1 text-[10px] text-[#8b96e8]">
                    今天
                  </span>
                )}
              </div>
              <div className="text-sm">
                {cell.matched.length > 0 ? `${cell.matched.length} 个任务` : (
                  <span className="text-[#5c616e]">无任务</span>
                )}
              </div>
              <div className="mt-auto flex gap-0.5">
                {cell.dots.map((dot) => (
                  <i
                    key={dot.category}
                    title={`${dot.label} ×${dot.count}`}
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: dot.color }}
                  />
                ))}
              </div>
            </button>
          )
        })}
      </div>

      <Typography.Text type="secondary" className="text-[11px]">
        数值为当日「任务种数」（去重，非触发次数）· 点击日期下钻日视图
      </Typography.Text>
    </div>
  )
}
