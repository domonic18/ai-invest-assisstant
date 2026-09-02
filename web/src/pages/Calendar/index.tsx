import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { Button, Card, Segmented, Spin, Tag, Typography } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'

import { useCalendarEvents } from '@/hooks/useCalendarEvents'
import type { CalendarEvent, CalendarEventCategory } from '@ai-invest/shared'

import { CALENDAR_CATEGORIES } from '@ai-invest/shared'

import { EventDrawer } from './EventDrawer'
import { ListView } from './ListView'
import { MonthView } from './MonthView'
import { WeekView } from './WeekView'
import { mondayOf } from './weekRange'

type CalendarView = 'month' | 'week' | 'list'

const VIEW_OPTIONS = [
  { label: '月历', value: 'month' },
  { label: '周历', value: 'week' },
  { label: '列表', value: 'list' },
]

export function Calendar() {
  const [view, setView] = useState<CalendarView>('month')
  const [month, setMonth] = useState<Dayjs>(() => dayjs().startOf('month'))
  const [weekAnchor, setWeekAnchor] = useState<Dayjs>(() => dayjs())
  const [selectedCategories, setSelectedCategories] = useState<Set<CalendarEventCategory>>(new Set())
  const [activeEvent, setActiveEvent] = useState<CalendarEvent | null>(null)

  const weekStart = mondayOf(weekAnchor)
  const range =
    view === 'week'
      ? { start: weekStart, end: weekStart.add(6, 'day') }
      : { start: month.startOf('month'), end: month.endOf('month') }

  const { data: events, isLoading } = useCalendarEvents(
    range.start.format('YYYY-MM-DD'),
    range.end.format('YYYY-MM-DD'),
  )

  const filteredEvents = useMemo(
    () =>
      selectedCategories.size
        ? (events ?? []).filter((e) => selectedCategories.has(e.category))
        : events ?? [],
    [events, selectedCategories],
  )

  const countByCategory = useMemo(() => {
    const counts = new Map<CalendarEventCategory, number>()
    for (const event of events ?? []) {
      counts.set(event.category, (counts.get(event.category) ?? 0) + 1)
    }
    return counts
  }, [events])

  const toggleCategory = (category: CalendarEventCategory) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(category)) next.delete(category)
      else next.add(category)
      return next
    })
  }

  const stepRange = (dir: 1 | -1) => {
    if (view === 'week') setWeekAnchor((prev) => mondayOf(prev).add(7 * dir, 'day'))
    else setMonth((prev) => prev.add(dir, 'month'))
  }

  const backToToday = () => {
    setMonth(dayjs().startOf('month'))
    setWeekAnchor(dayjs())
  }

  const navLabel =
    view === 'week'
      ? `${weekStart.format('MM-DD')} — ${weekStart.add(6, 'day').format('MM-DD')}`
      : month.format('YYYY 年 M 月')

  const isCurrentPeriod =
    view === 'week'
      ? weekStart.isSame(mondayOf(dayjs()), 'day')
      : month.isSame(dayjs(), 'month')

  return (
    <div className="space-y-4">
      <Typography.Title level={4} className="!mb-0">
        投资日历
      </Typography.Title>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Segmented options={VIEW_OPTIONS} value={view} onChange={(v) => setView(v as CalendarView)} />
        <div className="flex items-center gap-2">
          <Button size="small" icon={<LeftOutlined />} onClick={() => stepRange(-1)} />
          <span className="text-sm font-semibold font-mono">{navLabel}</span>
          <Button size="small" icon={<RightOutlined />} onClick={() => stepRange(1)} />
          {!isCurrentPeriod && (
            <Button size="small" type="link" onClick={backToToday}>
              回到今天
            </Button>
          )}
        </div>
      </div>

      <div className="flex gap-2 flex-wrap">
        <Tag.CheckableTag
          checked={selectedCategories.size === 0}
          onChange={() => setSelectedCategories(new Set())}
          className="!border !border-white/10"
        >
          全部 <span className="font-mono">{events?.length ?? 0}</span>
        </Tag.CheckableTag>
        {CALENDAR_CATEGORIES.map((category) => (
          <Tag.CheckableTag
            key={category}
            checked={selectedCategories.has(category)}
            onChange={() => toggleCategory(category)}
            className="!border !border-white/10"
          >
            {category} <span className="font-mono">{countByCategory.get(category) ?? 0}</span>
          </Tag.CheckableTag>
        ))}
      </div>

      <Spin spinning={isLoading}>
        <Card variant="borderless">
          {view === 'month' && (
            <MonthView month={month} events={filteredEvents} onSelectEvent={setActiveEvent} />
          )}
          {view === 'week' && (
            <WeekView weekAnchor={weekAnchor} events={filteredEvents} onSelectEvent={setActiveEvent} />
          )}
          {view === 'list' && (
            <ListView month={month} events={filteredEvents} onSelectEvent={setActiveEvent} />
          )}
        </Card>
      </Spin>

      <EventDrawer event={activeEvent} onClose={() => setActiveEvent(null)} />
    </div>
  )
}
