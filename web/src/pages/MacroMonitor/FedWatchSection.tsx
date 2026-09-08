import { Empty, Spin, Tag } from 'antd'
import dayjs from 'dayjs'
import type { FedWatchMeeting } from '@ai-invest/shared'

import { useUpcomingCalendarEvents } from '@/hooks/useCalendarEvents'
import { useFedWatch } from '@/hooks/useMarket'
import { useColorScheme } from '@/stores/settings'

const CUT_COLOR = '#5e6ad2'
const HOLD_COLOR = '#58a6ff'
const HIKE_COLOR = '#8a8f98'

/** 目标区间 bps → 百分比区间文案（375-400 → 3.75-4.00%）。 */
function rangeLabel(low: number, high: number): string {
  return `${(low / 100).toFixed(2)}-${(high / 100).toFixed(2)}%`
}

interface ProbRowProps {
  label: string
  prob: number
  color: string
}

function ProbRow({ label, prob, color }: ProbRowProps) {
  return (
    <div className="flex items-center gap-2.5 text-xs">
      <span className="w-[88px] shrink-0 text-gray-400">{label}</span>
      <div className="flex-1 h-3 rounded-md bg-[#181a21] overflow-hidden">
        <div
          className="h-full rounded-md"
          style={{ width: `${Math.min(prob, 100)}%`, background: color }}
        />
      </div>
      <span className="w-11 text-right font-mono font-semibold text-gray-200">
        {prob.toFixed(1)}%
      </span>
    </div>
  )
}

function FedWatchCard() {
  useColorScheme()
  const { data, isLoading } = useFedWatch()

  if (isLoading) {
    return (
      <div className="min-h-[118px] flex items-center justify-center rounded-xl border border-gray-800">
        <Spin />
      </div>
    )
  }
  if (!data || data.meetings.length === 0) {
    return (
      <div className="min-h-[118px] flex items-center justify-center rounded-xl border border-gray-800">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无 FedWatch 数据（每日 07:30 采集后可用）"
        />
      </div>
    )
  }

  const next: FedWatchMeeting = data.meetings[0]
  const meetingDay = dayjs(next.meetingDate)
  const daysToMeet = meetingDay.startOf('day').diff(dayjs().startOf('day'), 'day')

  return (
    <div
      className="col-span-2 flex flex-col gap-1 rounded-xl border border-gray-800 p-3.5 px-4"
    >
      <div className="flex items-center gap-1.5">
        <span className="text-[13px] font-medium text-gray-400">
          美联储 {meetingDay.format('M 月')}议息概率
        </span>
        <Tag color="purple" className="!mr-0 !text-[11px] !leading-4 !px-2">
          政策
        </Tag>
      </div>
      <div className="flex flex-col gap-2 mt-1.5">
        <ProbRow label="降息（累计）" prob={next.probCut} color={CUT_COLOR} />
        <ProbRow label="维持不变" prob={next.probHold} color={HOLD_COLOR} />
        <ProbRow label="加息（累计）" prob={next.probHike} color={HIKE_COLOR} />
      </div>
      <div className="flex items-center justify-between text-[10px] text-gray-600 mt-2.5">
        <span>CME FedWatch · 截至 {dayjs(data.dataAsAt).format('MM-DD HH:mm')} CT</span>
        <span>
          最可能区间 {rangeLabel(next.likelyRangeLow, next.likelyRangeHigh)}
          {daysToMeet > 0 ? ` · T-${daysToMeet}天` : ''}
        </span>
      </div>
    </div>
  )
}

function MeetingScheduleCard() {
  useColorScheme()
  const { data: events, isLoading } = useUpcomingCalendarEvents(10)

  const rows = (events ?? [])
    .filter((e) => e.category === '宏观' || e.category === '央行动态')
    .slice(0, 5)

  return (
    <div className="flex flex-col gap-1 rounded-xl border border-gray-800 p-3.5 px-4 min-h-[118px]">
      <div className="flex items-center gap-1.5">
        <span className="text-[13px] font-medium text-gray-400">议息日程提醒</span>
        <Tag color="blue" className="!mr-0 !text-[11px] !leading-4 !px-2">
          日历
        </Tag>
      </div>
      {isLoading ? (
        <div className="flex justify-center py-3">
          <Spin size="small" />
        </div>
      ) : rows.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          className="py-2"
          description="暂无宏观日程"
        />
      ) : (
        <div className="flex flex-col gap-2 mt-1.5 text-xs text-gray-400">
          {rows.map((e) => {
            const day = dayjs(e.eventTime)
            const days = day.startOf('day').diff(dayjs().startOf('day'), 'day')
            const isFomc = /fomc/i.test(e.title)
            return (
              <div key={e.id} className="flex items-center justify-between gap-2">
                <span className="font-mono text-gray-600 shrink-0">
                  {day.format('MM-DD')}
                </span>
                <span className="flex-1 truncate" title={e.title}>
                  {e.title}
                </span>
                {days < 0 ? (
                  <Tag color="green" className="!mr-0 !text-[11px] !leading-4">
                    已公布
                  </Tag>
                ) : (
                  <Tag
                    color={isFomc ? 'red' : 'orange'}
                    className="!mr-0 !text-[11px] !leading-4"
                  >
                    {days === 0 ? '今天' : `T-${days}天`}
                  </Tag>
                )}
              </div>
            )
          })}
        </div>
      )}
      <div className="text-[10px] text-gray-600 mt-auto pt-2">
        与投资日历联动（FOMC / CPI 高亮）
      </div>
    </div>
  )
}

export function FedWatchSection() {
  return (
    <div className="grid grid-cols-2 gap-3">
      <FedWatchCard />
      <MeetingScheduleCard />
    </div>
  )
}
