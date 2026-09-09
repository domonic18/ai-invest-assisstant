import { fireEvent, render, screen } from '@testing-library/react'
import dayjs, { type Dayjs } from 'dayjs'
import { describe, expect, it, vi } from 'vitest'

import type { CalendarEvent } from '@ai-invest/shared'

vi.mock('@/hooks/useCalendarEvents', () => ({
  useCalendarEvents: vi.fn(),
}))
vi.mock('@/hooks/useWatchlistGroups', () => ({
  useWatchlistGroups: vi.fn(),
}))

import { useCalendarEvents } from '@/hooks/useCalendarEvents'
import { useWatchlistGroups } from '@/hooks/useWatchlistGroups'

import { Calendar } from './index'

const mockEvents = vi.mocked(useCalendarEvents)
const mockGroups = vi.mocked(useWatchlistGroups)

/** 本地正午时刻，保证 eventTime 在任何时区下都落在同一日历日。 */
function noonISO(day: Dayjs): string {
  return day.hour(12).minute(0).second(0).millisecond(0).toISOString()
}

function event(id: number, day: Dayjs, overrides: Partial<CalendarEvent> = {}): CalendarEvent {
  return {
    id,
    eventTime: noonISO(day),
    endTime: null,
    title: `事件 ${id}`,
    category: '宏观',
    impactMarkets: ['中国'],
    source: 'cls',
    sourceUrl: null,
    relatedSymbols: [],
    ...overrides,
  }
}

/** 与当前月同月的相邻日（月末安全），保证落在月历网格内。 */
function neighborDay(): Dayjs {
  const today = dayjs()
  return today.add(1, 'day').isSame(today, 'month') ? today.add(1, 'day') : today.subtract(1, 'day')
}

function setup(events: CalendarEvent[], groups: unknown[] = []) {
  mockEvents.mockReturnValue({
    data: events,
    isLoading: false,
  } as unknown as ReturnType<typeof useCalendarEvents>)
  mockGroups.mockReturnValue({ data: groups } as unknown as ReturnType<typeof useWatchlistGroups>)
  return render(<Calendar />)
}

describe('Calendar', () => {
  it('renders subtitle and today events in persistent detail panel', () => {
    setup([event(1, dayjs(), { title: '今日宏观数据发布' })])

    // 页头副标题：数据来源与 ★ 图例
    expect(screen.getByText(/数据来源：财联社日历/)).toBeInTheDocument()
    // 详情常驻面板默认展示今天的事件（月历 chip 与面板标题同时命中）
    expect(screen.getAllByText('今日宏观数据发布').length).toBeGreaterThan(0)
    expect(screen.getByText('事件时间')).toBeInTheDocument()
    expect(screen.getByText('财联社日历')).toBeInTheDocument()
  })

  it('clicking a day chip switches the detail panel to that day', () => {
    const other = neighborDay()
    setup([
      event(1, dayjs(), { title: '今日宏观数据发布' }),
      event(2, other, { title: '华卓精科申购' }),
    ])

    expect(screen.getAllByText('今日宏观数据发布').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText((c) => c.includes('华卓精科申购')))
    // 面板头部切到选中日（MM-DD 周X），事件详情出现在面板中
    expect(
      screen.getByText((c) => c.startsWith(other.format('MM-DD')) && c.includes('周')),
    ).toBeInTheDocument()
    expect(screen.getAllByText((c) => c.includes('华卓精科申购')).length).toBeGreaterThan(0)
  })

  it('marks events whose related symbols hit the watchlist', () => {
    const starred = event(1, dayjs(), {
      title: '宁德时代解禁',
      relatedSymbols: ['宁德时代 300750'],
    })
    const { container, rerender } = setup([starred])

    // 自选为空：仅副标题与数据说明卡 2 处图例 ★
    expect(container.querySelectorAll('.text-amber-400').length).toBe(2)

    setup([starred], [
      { id: 1, name: '默认分组', items: [{ id: 'a', code: '300750', tags: [] }] },
    ])
    rerender(<Calendar />)
    // 命中自选：月历 chip + 详情面板标题/标的 共 ≥4 处 ★
    expect(container.querySelectorAll('.text-amber-400').length).toBeGreaterThanOrEqual(4)
  })

  it('shows 休市 empty state for weekend columns in week view', () => {
    setup([event(1, dayjs())])

    fireEvent.click(screen.getByText('周历'))
    expect(screen.getAllByText('休市').length).toBeGreaterThanOrEqual(1)
  })

  it('collapses and expands the detail column with persisted state', () => {
    setup([event(1, dayjs(), { title: '今日宏观数据发布' })])

    fireEvent.click(screen.getByRole('button', { name: '收起事件详情' }))
    expect(screen.queryByText('事件详情')).not.toBeInTheDocument()
    expect(screen.queryByText('数据说明')).not.toBeInTheDocument()
    expect(localStorage.getItem('settings:calendar-detail-collapsed')).toBe('1')

    fireEvent.click(screen.getByRole('button', { name: '展开事件详情' }))
    expect(screen.getByText('事件详情')).toBeInTheDocument()
    expect(localStorage.getItem('settings:calendar-detail-collapsed')).toBe('0')
  })
})
