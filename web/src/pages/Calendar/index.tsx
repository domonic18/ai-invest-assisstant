import { LeftOutlined, MenuFoldOutlined, MenuUnfoldOutlined, RightOutlined } from '@ant-design/icons'
import { Button, Card, Segmented, Spin, Tag, Tooltip, Typography } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useMemo, useState } from 'react'

import { useCalendarEvents } from '@/hooks/useCalendarEvents'
import { useWatchlistGroups } from '@/hooks/useWatchlistGroups'
import { useSettingsStore } from '@/stores/settings'
import type { CalendarEventCategory } from '@ai-invest/shared'

import { CALENDAR_CATEGORIES } from '@ai-invest/shared'

import { EventDetailPanel } from './EventDetailPanel'
import { DOW_LABELS_SUN_FIRST } from './eventMeta'
import { ListView } from './ListView'
import { MonthView } from './MonthView'
import { WeekView } from './WeekView'
import { mondayOf } from './weekRange'

import { DATE_FORMAT } from '@/utils/formatters'

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
  const [selectedDay, setSelectedDay] = useState<Dayjs>(() => dayjs())
  const [selectedCategories, setSelectedCategories] = useState<Set<CalendarEventCategory>>(new Set())
  const detailCollapsed = useSettingsStore((s) => s.calendarDetailCollapsed)
  const toggleDetailCollapsed = useSettingsStore((s) => s.toggleCalendarDetailCollapsed)

  const weekStart = mondayOf(weekAnchor)
  const range =
    view === 'week'
      ? { start: weekStart, end: weekStart.add(6, 'day') }
      : { start: month.startOf('month'), end: month.endOf('month') }

  const { data: events, isLoading } = useCalendarEvents(
    range.start.format(DATE_FORMAT),
    range.end.format(DATE_FORMAT),
  )
  const { data: groups } = useWatchlistGroups()
  const watchlistCodes = useMemo(
    () => new Set((groups ?? []).flatMap((g) => g.items.map((i) => i.code))),
    [groups],
  )

  const filteredEvents = useMemo(
    () =>
      selectedCategories.size
        ? (events ?? []).filter((e) => selectedCategories.has(e.category))
        : events ?? [],
    [events, selectedCategories],
  )

  const selectedDayEvents = useMemo(
    () =>
      filteredEvents.filter(
        (e) => dayjs(e.eventTime).format(DATE_FORMAT) === selectedDay.format(DATE_FORMAT),
      ),
    [filteredEvents, selectedDay],
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

  // 翻页时选中日随区间平移，保证详情面板始终落在已取数范围内
  const stepRange = (dir: 1 | -1) => {
    if (view === 'week') {
      setWeekAnchor((prev) => mondayOf(prev).add(7 * dir, 'day'))
      setSelectedDay((prev) => prev.add(7 * dir, 'day'))
    } else {
      setMonth((prev) => prev.add(dir, 'month'))
      setSelectedDay((prev) => prev.add(dir, 'month'))
    }
  }

  const backToToday = () => {
    setMonth(dayjs().startOf('month'))
    setWeekAnchor(dayjs())
    setSelectedDay(dayjs())
  }

  const navLabel =
    view === 'week'
      ? `${weekStart.format('MM-DD')} — ${weekStart.add(6, 'day').format('MM-DD')}`
      : month.format('YYYY 年 M 月')

  const isCurrentPeriod =
    view === 'week'
      ? weekStart.isSame(mondayOf(dayjs()), 'day')
      : month.isSame(dayjs(), 'month')

  const today = dayjs()

  return (
    <div className="space-y-4">
      <div>
        <Typography.Title level={4} className="!mb-0">
          投资日历
        </Typography.Title>
        <div className="mt-1 text-xs opacity-50">
          {today.format('YYYY-MM-DD')} 周{DOW_LABELS_SUN_FIRST[today.day()]} · 数据来源：财联社日历 +
          Fed/BLS 固定日程 · <span className="text-amber-400">★</span> = 关联标的在自选股中
        </div>
      </div>

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
          <Tooltip title={detailCollapsed ? '展开事件详情' : '收起事件详情'}>
            <Button
              size="small"
              aria-label={detailCollapsed ? '展开事件详情' : '收起事件详情'}
              icon={detailCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={toggleDetailCollapsed}
            />
          </Tooltip>
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

      <div
        className={`grid grid-cols-1 gap-4 items-start ${
          detailCollapsed ? '' : 'xl:grid-cols-[2fr_1fr]'
        }`}
      >
        <Spin spinning={isLoading} wrapperClassName="min-w-0">
          <Card variant="borderless">
            {view === 'month' && (
              <MonthView
                month={month}
                events={filteredEvents}
                selectedDay={selectedDay}
                onSelectDay={setSelectedDay}
                watchlistCodes={watchlistCodes}
              />
            )}
            {view === 'week' && (
              <WeekView
                weekAnchor={weekAnchor}
                events={filteredEvents}
                selectedDay={selectedDay}
                onSelectDay={setSelectedDay}
                watchlistCodes={watchlistCodes}
              />
            )}
            {view === 'list' && (
              <ListView
                month={month}
                events={filteredEvents}
                onSelectDay={setSelectedDay}
                watchlistCodes={watchlistCodes}
              />
            )}
          </Card>
        </Spin>

        {!detailCollapsed && (
          <div className="space-y-4 min-w-0">
            <EventDetailPanel
              day={selectedDay}
              events={selectedDayEvents}
              watchlistCodes={watchlistCodes}
            />
            <Card variant="borderless" title="数据说明">
              <div className="space-y-2 text-xs opacity-60 leading-relaxed">
                <p>
                  事件由采集任务每日增量写入 <code className="font-mono">calendar_event</code>{' '}
                  表，财联社日历 + Fed/BLS 固定日程两路来源，按{' '}
                  <code className="font-mono">source_hash</code> 幂等去重。
                </p>
                <p>
                  分类：宏观 / 央行动态 / 新股 / 解禁 / 财报 / 会议；
                  <span className="text-amber-400">★</span>{' '}
                  标记表示事件关联标的命中自选股，工作台日历摘要卡仅展示近 7 日事件。
                </p>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
