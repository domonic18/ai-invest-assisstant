/** 任务日历容器：日/周/月三档切换 + 业务分类筛选 chips + 仅启用开关 + 图例。 */

import { DatePicker, Segmented, Spin, Switch } from 'antd'
import type { Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'

import type { AdminTask } from '@ai-invest/shared'

import { TASK_CATEGORY_META } from '@/utils/taskCategoryMeta'

import { DayView } from './DayView'
import { MonthView } from './MonthView'
import { WeekView } from './WeekView'
import { buildCalendarTasks, todayBj, type CalendarTask } from './calendarUtils'

type Granularity = 'day' | 'week' | 'month'

interface TaskCalendarProps {
  tasks: AdminTask[]
  loading: boolean
  onOpenDetail: (task: AdminTask) => void
}

export function TaskCalendar({ tasks, loading, onOpenDetail }: TaskCalendarProps) {
  const [gran, setGran] = useState<Granularity>('week')
  const [onlyActive, setOnlyActive] = useState(true)
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(
    () => new Set(Object.keys(TASK_CATEGORY_META)),
  )
  const [dayDate, setDayDate] = useState<Dayjs>(() => todayBj())
  const [monthDate, setMonthDate] = useState<Dayjs>(() => todayBj().startOf('month'))

  const calendarTasks = useMemo(() => buildCalendarTasks(tasks), [tasks])

  const filtered = useMemo(
    () =>
      calendarTasks.filter((task) => {
        if (onlyActive && !taskShowsActive(tasks, task)) return false
        return selectedCategories.has(task.category)
      }),
    [calendarTasks, onlyActive, selectedCategories, tasks],
  )

  const handleOpen = (taskKey: string) => {
    const task = tasks.find((t) => String(t.id) === taskKey)
    if (task) onOpenDetail(task)
  }

  const toggleCategory = (category: string) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(category)) {
        if (next.size > 1) next.delete(category)
      } else {
        next.add(category)
      }
      return next
    })
  }

  if (loading) {
    return <Spin className="flex justify-center py-10" />
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <Segmented
          value={gran}
          onChange={(value) => setGran(value as Granularity)}
          options={[
            { value: 'day', label: '日' },
            { value: 'week', label: '周' },
            { value: 'month', label: '月' },
          ]}
        />
        {gran === 'day' && (
          <DatePicker
            value={dayDate}
            allowClear={false}
            onChange={(value) => value && setDayDate(value)}
          />
        )}
        <Switch
          checkedChildren="仅启用"
          unCheckedChildren="全部"
          checked={onlyActive}
          onChange={setOnlyActive}
        />
        <span className="text-xs text-[#8a8f98]">
          {gran === 'week' && '通用周 · 高频任务聚合为带状色块'}
          {gran === 'day' && `${filtered.length} 个任务`}
          {gran === 'month' && '数值为当日任务种数 · 点击日期下钻'}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {Object.entries(TASK_CATEGORY_META).map(([key, meta]) => {
          const active = selectedCategories.has(key)
          return (
            <button
              key={key}
              type="button"
              onClick={() => toggleCategory(key)}
              className={`flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
                active
                  ? 'border-white/20 bg-white/[0.06] text-[#f0f1f5]'
                  : 'border-white/10 text-[#5c616e]'
              }`}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: active ? meta.color : undefined, border: active ? 'none' : `1px solid ${meta.color}` }}
              />
              {meta.label}
            </button>
          )
        })}
      </div>

      {gran === 'week' && <WeekView tasks={filtered} onOpen={handleOpen} />}
      {gran === 'day' && <DayView tasks={filtered} date={dayDate} onOpen={handleOpen} />}
      {gran === 'month' && (
        <MonthView
          tasks={filtered}
          month={monthDate}
          onMonthChange={setMonthDate}
          onDrillDay={(date) => {
            setDayDate(date)
            setGran('day')
          }}
        />
      )}

      <div className="flex flex-wrap gap-3 border-t border-white/10 pt-2">
        {Object.entries(TASK_CATEGORY_META).map(([key, meta]) => (
          <span key={key} className="flex items-center gap-1 text-[11px] text-[#8a8f98]">
            <span className="h-2 w-2 rounded-full" style={{ background: meta.color }} />
            {meta.label}
          </span>
        ))}
      </div>
    </div>
  )
}

function taskShowsActive(tasks: AdminTask[], task: CalendarTask): boolean {
  return tasks.some((t) => String(t.id) === task.key && t.isActive)
}
